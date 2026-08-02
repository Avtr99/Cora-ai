"""LLM connection-test helpers and route for the LLM settings routes."""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...query_processing.llm_factory import get_llm_settings


class LLMTestResponse(BaseModel):
    """Result of an LLM connection test."""
    success: bool = Field(..., description="Whether the test succeeded")
    message: str = Field(..., description="Human-readable result message")
    detail: Optional[str] = Field(None, description="Technical error detail (on failure)")


class LLMTestRequest(BaseModel):
    """Request body for POST /v1/settings/llm/test.

    If api_key is None, the existing saved key is used (so users can re-test
    without re-entering the key).
    """
    provider: str = Field(..., description="Provider: 'gemini' or 'openai_compatible'")
    api_key: Optional[str] = Field(None, description="API key to test. If None, uses the existing saved key.")
    base_url: Optional[str] = Field(None, description="Base URL for OpenAI-compatible providers")
    model_main: Optional[str] = Field(None, description="Model name to test")


router = APIRouter()


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
        # Ollama uses /v1 too -- only auto-append for non-Ollama
        if "localhost:11434" not in base_url and "127.0.0.1:11434" not in base_url:
            base_url = base_url.rstrip("/") + "/v1"

    try:
        client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=15.0)
        # Minimal chat completion -- keeps cost negligible.
        # Reasoning models (GPT-5.x, o1/o3/o4) reject max_tokens and temperature;
        # use max_completion_tokens and omit temperature for those models.
        lower_model = (model or "").lower()
        bare_model = lower_model.rsplit("/", 1)[-1]
        is_reasoning = any(bare_model.startswith(p) for p in ("gpt-5", "o1", "o3", "o4"))
        create_kwargs: dict = {
            "model": model,
            "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        }
        if is_reasoning:
            create_kwargs["max_completion_tokens"] = 5
        else:
            create_kwargs["max_tokens"] = 5
        response = await client.chat.completions.create(**create_kwargs)
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


@router.post("/llm/test", response_model=LLMTestResponse)
async def test_llm_config(req: LLMTestRequest) -> LLMTestResponse:
    """Test an LLM configuration before saving it.

    Makes a lightweight API call to verify that:
    - The API key is valid
    - The model name exists and is accessible
    - The base URL is reachable (for OpenAI-compatible providers)

    This does NOT save the settings -- it only validates them.
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
