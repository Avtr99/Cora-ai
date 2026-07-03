"""LLM provider settings routes."""

from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from loguru import logger
import httpx

from ...config import get_settings
from ...query_processing.llm_factory import (
    get_llm_settings,
    save_llm_settings,
    is_llm_configured,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class LLMSettingsResponse(BaseModel):
    """Response model for GET /v1/settings/llm.

    Note: The API key is NEVER returned. Only `has_api_key: true/false`.
    """
    is_configured: bool = Field(..., description="Whether an LLM provider is configured")
    provider: Optional[str] = Field(None, description="Active provider: 'gemini' or 'openai_compatible'")
    has_api_key: bool = Field(False, description="Whether an API key is set (key itself is never returned)")
    base_url: Optional[str] = Field(None, description="Base URL for OpenAI-compatible providers")
    model_main: Optional[str] = Field(None, description="Primary model name")
    model_lite: Optional[str] = Field(None, description="Lite model name for low-latency tasks")
    model_relevance: Optional[str] = Field(None, description="Model for post-generation relevance check (defaults to model_lite)")
    organization: Optional[str] = Field(None, description="OpenAI organization ID (if set)")


class LLMSettingsUpdate(BaseModel):
    """Request model for PUT /v1/settings/llm."""
    provider: str = Field(..., description="Provider: 'gemini' or 'openai_compatible'")
    api_key: Optional[str] = Field(None, description="API key. If None, existing key is preserved.")
    base_url: Optional[str] = Field(None, description="Base URL for OpenAI-compatible providers")
    model_main: Optional[str] = Field(None, description="Primary model name")
    model_lite: Optional[str] = Field(None, description="Lite model name (optional)")
    model_relevance: Optional[str] = Field(None, description="Model for post-generation relevance check (optional)")
    organization: Optional[str] = Field(None, description="OpenAI organization ID (optional)")


class LLMModel(BaseModel):
    """A single available model from a provider."""
    name: str
    size_bytes: Optional[int] = None
    parameter_size: Optional[str] = None
    family: Optional[str] = None


class LLMModelsResponse(BaseModel):
    """Response model for GET /v1/settings/llm/models."""
    models: List[LLMModel]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/llm", response_model=LLMSettingsResponse)
async def get_llm_config() -> LLMSettingsResponse:
    """Get current LLM provider configuration.

    **Security:** The API key is never returned. Only `has_api_key: true/false`.
    """
    settings = get_llm_settings()
    env_settings = get_settings()
    # When using .env fallback, model_main may be None — fill in the
    # defaults from the Settings singleton so the UI shows the actual model.
    model_main = settings["model_main"]
    model_lite = settings["model_lite"]
    if settings["provider"] == "gemini":
        if not model_main:
            model_main = env_settings.GEMINI_MODEL_MAIN
        if not model_lite:
            model_lite = env_settings.GEMINI_MODEL_LITE
    return LLMSettingsResponse(
        is_configured=is_llm_configured(),
        provider=settings["provider"],
        has_api_key=settings["api_key"] is not None,
        base_url=settings["base_url"],
        model_main=model_main,
        model_lite=model_lite,
        model_relevance=settings["model_relevance"],
        organization=settings["organization"],
    )


@router.put("/llm", response_model=LLMSettingsResponse)
async def update_llm_config(update: LLMSettingsUpdate) -> LLMSettingsResponse:
    """Update LLM provider configuration.

    If `api_key` is None, the existing key is preserved (not overwritten).
    After updating, the application must be restarted for the new client
    to take effect (or the client re-initialized via lifespan).
    """
    if update.provider not in ("gemini", "openai_compatible"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider '{update.provider}'. Must be 'gemini' or 'openai_compatible'."
        )

    if update.provider == "openai_compatible" and not update.base_url:
        # Default to OpenAI's endpoint if not specified
        update.base_url = "https://api.openai.com/v1"

    try:
        save_llm_settings(
            provider=update.provider,
            api_key=update.api_key,
            base_url=update.base_url,
            model_main=update.model_main,
            model_lite=update.model_lite,
            model_relevance=update.model_relevance,
            organization=update.organization,
        )
        logger.info(f"LLM settings updated: provider={update.provider}")
    except Exception as e:
        logger.error(f"Failed to save LLM settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {e}")

    # Return the updated settings
    settings = get_llm_settings()
    return LLMSettingsResponse(
        is_configured=is_llm_configured(),
        provider=settings["provider"],
        has_api_key=settings["api_key"] is not None,
        base_url=settings["base_url"],
        model_main=settings["model_main"],
        model_lite=settings["model_lite"],
        model_relevance=settings["model_relevance"],
        organization=settings["organization"],
    )


@router.get("/llm/models", response_model=LLMModelsResponse)
async def list_llm_models(base_url: str) -> LLMModelsResponse:
    """List available models from a provider.

    Currently supports Ollama's native `/api/tags` endpoint.
    For OpenAI and other providers, the user enters the model name manually.

    Query parameter:
        base_url: The provider's base URL (e.g. http://localhost:11434 for Ollama)
    """
    if not base_url:
        raise HTTPException(status_code=400, detail="base_url query parameter is required")

    # Detect Ollama by the default port or URL pattern
    is_ollama = "localhost:11434" in base_url or "127.0.0.1:11434" in base_url

    if is_ollama:
        try:
            return await _list_ollama_models(base_url)
        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail=f"Could not connect to Ollama at {base_url}. Is `ollama serve` running?"
            )
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
            raise HTTPException(status_code=502, detail=f"Failed to fetch models from Ollama: {e}")

    # For other OpenAI-compatible providers, return empty list (user enters name manually)
    return LLMModelsResponse(models=[])


async def _list_ollama_models(base_url: str) -> LLMModelsResponse:
    """Fetch installed models from Ollama's /api/tags endpoint."""
    # Ensure base_url doesn't have trailing slash
    url = base_url.rstrip("/") + "/api/tags"

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

    models = []
    for m in data.get("models", []):
        details = m.get("details", {}) or {}
        models.append(LLMModel(
            name=m.get("name", ""),
            size_bytes=m.get("size"),
            parameter_size=details.get("parameter_size"),
            family=details.get("family"),
        ))

    return LLMModelsResponse(models=models)


# ---------------------------------------------------------------------------
# LLM connection test (validate before saving)
# ---------------------------------------------------------------------------

class LLMTestRequest(BaseModel):
    """Request body for POST /v1/settings/llm/test.

    If api_key is None, the existing saved key is used (so users can re-test
    without re-entering the key).
    """
    provider: str = Field(..., description="Provider: 'gemini' or 'openai_compatible'")
    api_key: Optional[str] = Field(None, description="API key to test. If None, uses the existing saved key.")
    base_url: Optional[str] = Field(None, description="Base URL for OpenAI-compatible providers")
    model_main: Optional[str] = Field(None, description="Model name to test")


class LLMTestResponse(BaseModel):
    """Result of an LLM connection test."""
    success: bool = Field(..., description="Whether the test succeeded")
    message: str = Field(..., description="Human-readable result message")
    detail: Optional[str] = Field(None, description="Technical error detail (on failure)")


@router.post("/llm/test", response_model=LLMTestResponse)
async def test_llm_config(req: LLMTestRequest) -> LLMTestResponse:
    """Test an LLM configuration before saving it.

    Makes a lightweight API call to verify that:
    - The API key is valid
    - The model name exists and is accessible
    - The base URL is reachable (for OpenAI-compatible providers)

    This does NOT save the settings — it only validates them.
    """
    if req.provider not in ("gemini", "openai_compatible"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider '{req.provider}'. Must be 'gemini' or 'openai_compatible'."
        )

    # Resolve the API key: use the request value, or fall back to the saved key
    api_key = req.api_key
    if not api_key:
        existing = get_llm_settings()
        api_key = existing["api_key"]
    if not api_key:
        # For Ollama, a dummy key is fine
        base_url = req.base_url or ""
        if "localhost:11434" in base_url or "127.0.0.1:11434" in base_url:
            api_key = "ollama"
        else:
            return LLMTestResponse(
                success=False,
                message="No API key provided. Enter an API key to test.",
                detail="api_key is None and no existing key was found",
            )

    model = req.model_main or "test"
    base_url = req.base_url

    if req.provider == "gemini":
        return await _test_gemini(api_key, model)
    else:
        if not base_url:
            return LLMTestResponse(
                success=False,
                message="Base URL is required for OpenAI-compatible providers.",
            )
        return await _test_openai_compatible(api_key, base_url, model)


async def _test_gemini(api_key: str, model: str) -> LLMTestResponse:
    """Test a Gemini API key + model by making a minimal generate_content call."""
    try:
        from google import genai
        from google.genai import types as gtypes
    except ImportError:
        return LLMTestResponse(
            success=False,
            message="The 'google-genai' package is not installed on the backend.",
            detail="ImportError: google.genai",
        )

    try:
        client = genai.Client(api_key=api_key)
        # Use a minimal prompt to keep cost negligible
        response = await client.aio.models.generate_content(
            model=model or "gemini-2.5-flash",
            contents="Reply with exactly: OK",
            config=gtypes.GenerateContentConfig(max_output_tokens=5),
        )
        # If we got here without raising, the key + model are valid
        text = response.text if hasattr(response, "text") else ""
        return LLMTestResponse(
            success=True,
            message=f"Connection successful. Model '{model or 'gemini-2.5-flash'}' responded.",
            detail=text[:50] if text else None,
        )
    except Exception as e:
        error_str = str(e)
        # Classify common errors for user-friendly messages
        if "API_KEY_INVALID" in error_str or "api_key" in error_str.lower() and "invalid" in error_str.lower():
            return LLMTestResponse(success=False, message="Invalid API key. Check your Gemini API key.", detail=error_str[:300])
        if "not_found" in error_str.lower() or "model" in error_str.lower() and "not" in error_str.lower():
            return LLMTestResponse(success=False, message=f"Model '{model}' not found. Check the model name.", detail=error_str[:300])
        if "permission" in error_str.lower() or "403" in error_str:
            return LLMTestResponse(success=False, message="API key does not have permission to access this model.", detail=error_str[:300])
        return LLMTestResponse(success=False, message="Connection failed. See detail for more info.", detail=error_str[:300])


async def _test_openai_compatible(api_key: str, base_url: str, model: str) -> LLMTestResponse:
    """Test an OpenAI-compatible provider by making a minimal chat completion call."""
    try:
        from openai import AsyncOpenAI
    except ImportError:
        return LLMTestResponse(
            success=False,
            message="The 'openai' package is not installed on the backend.",
            detail="ImportError: openai",
        )

    # Ensure base_url ends with /v1 for OpenAI-compatible endpoints
    if not base_url.rstrip("/").endswith("/v1"):
        # Ollama uses /v1 too — only auto-append for non-Ollama
        if "localhost:11434" not in base_url and "127.0.0.1:11434" not in base_url:
            base_url = base_url.rstrip("/") + "/v1"

    try:
        client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=15.0)
        # Minimal chat completion — keeps cost negligible
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            max_tokens=5,
        )
        # If we got here, the key + model + URL are all valid
        return LLMTestResponse(
            success=True,
            message=f"Connection successful. Model '{model}' responded.",
            detail=response.choices[0].message.content[:50] if response.choices else None,
        )
    except Exception as e:
        error_str = str(e)
        error_type = type(e).__name__

        # Classify common errors
        if "authentication" in error_str.lower() or "api_key" in error_str.lower() or "401" in error_str:
            return LLMTestResponse(success=False, message="Invalid API key. Check your API key for this provider.", detail=error_str[:300])
        if "model" in error_str.lower() and ("not" in error_str.lower() or "does not exist" in error_str.lower()):
            return LLMTestResponse(success=False, message=f"Model '{model}' not found. Check the model name.", detail=error_str[:300])
        if "connection" in error_str.lower() or "refused" in error_str.lower() or "timeout" in error_str.lower():
            return LLMTestResponse(success=False, message=f"Could not connect to {base_url}. Check the URL and that the service is running.", detail=error_str[:300])
        if "404" in error_str:
            return LLMTestResponse(success=False, message=f"Model '{model}' not found at {base_url}. Check the model name.", detail=error_str[:300])
        if error_type == "APIConnectionError":
            return LLMTestResponse(success=False, message=f"Could not connect to {base_url}. Is the service running?", detail=error_str[:300])

        return LLMTestResponse(success=False, message="Connection failed. See detail for more info.", detail=error_str[:300])
