"""LLM provider settings routes."""

from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from loguru import logger

from ...config import get_settings
from ...query_processing.llm_factory import (
    get_llm_settings,
    save_llm_settings,
    is_llm_configured,
)
from ...db.app_settings import save_app_setting
from ...db.llm_profile_manager import (
    _read_profile,
    _read_all_profiles,
    _save_profile,
    _label_for_openai,
    _slug,
    _detect_env_providers,
)
from .llm_ollama import LLMModelsResponse, _validate_ollama_url, _list_ollama_models
from .llm_test import LLMTestResponse, _test_gemini, _test_openai_compatible
from ..lifespan import hot_swap_llm_client

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


class ProviderSwitchRequest(BaseModel):
    """Request model for POST /v1/settings/llm/switch.

    Used by the chat provider toggle to instantly switch between providers.
    Takes a profile slug (e.g. "gemini", "openai", "openrouter") — not a
    provider type. The profile must already exist (saved via PUT /llm or
    detected from .env keys).
    """
    label: str = Field(
        ...,
        max_length=100,
        description="Profile slug to switch to (e.g. 'gemini', 'openai', 'openrouter')",
    )


class ProviderSwitchResponse(BaseModel):
    """Response model for POST /v1/settings/llm/switch."""
    success: bool
    label: Optional[str] = None
    provider: Optional[str] = None
    model_main: Optional[str] = None
    client_type: Optional[str] = None
    error: Optional[str] = None


class AvailableProvider(BaseModel):
    slug: str
    label: str
    provider: str
    model: str
    has_api_key: bool


class AvailableProvidersResponse(BaseModel):
    """Response model for GET /v1/settings/llm/providers."""
    current: Optional[str] = None
    available: List[AvailableProvider] = []


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
    The LLM client and RAG orchestrator are hot-swapped in-place after saving,
    so changes take effect immediately without a server restart.
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

    # Save as a profile so the chat toggle can switch back to this config.
    # Derive a label from the provider + base_url.
    if update.provider == "gemini":
        label = "gemini"
    else:
        label = _slug(_label_for_openai(update.base_url or ""))
    _save_profile(
        label, update.provider, update.api_key, update.base_url,
        update.model_main, update.model_lite, update.model_relevance, update.organization,
    )

    # Hot-swap the LLM client and orchestrator so changes take effect
    # immediately without a server restart.
    swap_result = await hot_swap_llm_client()
    if not swap_result["success"]:
        logger.warning(f"LLM settings saved but hot-swap failed: {swap_result.get('error')}")
    else:
        logger.info(f"LLM hot-swapped to {swap_result.get('client_type')} ({swap_result.get('model')})")

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


@router.post("/llm/switch", response_model=ProviderSwitchResponse)
async def switch_llm_provider(req: ProviderSwitchRequest) -> ProviderSwitchResponse:
    """Quick-switch the active LLM provider by profile label.

    Switches to a provider profile whose API key is already configured (in
    .env or saved via PUT /llm). The LLM client and orchestrator are hot-swapped
    in-place — no restart needed.

    The current config is saved as a profile before switching, so switching back
    restores it exactly.

    For initial provider setup (entering new API keys), use PUT /v1/settings/llm.
    """
    # ponytail: no lock — local-first single-user app, concurrent switches are
    # not a real concern. If two switches race, the last one wins.
    env_settings = get_settings()
    current_settings = get_llm_settings()

    # Save current config as a profile so switching back restores it
    if current_settings["provider"]:
        cur_label = "gemini" if current_settings["provider"] == "gemini" else \
            _slug(_label_for_openai(current_settings["base_url"] or ""))
        _save_profile(
            cur_label, current_settings["provider"],
            current_settings["api_key"], current_settings["base_url"],
            current_settings["model_main"], current_settings["model_lite"],
            current_settings["model_relevance"], current_settings["organization"],
        )

    # Find the target profile: saved DB profile first, then .env-detected
    profile = _read_profile(req.label)
    if not profile:
        # Check .env-detected providers
        for p in _detect_env_providers(env_settings):
            if p["slug"] == req.label:
                profile = p
                break

    if not profile:
        raise HTTPException(
            status_code=400,
            detail=f"No profile found for '{req.label}'. Configure it via Settings first."
        )

    provider = profile["provider"]
    save_llm_settings(
        provider=provider,
        api_key=profile.get("api_key"),
        base_url=profile.get("base_url"),
        model_main=profile.get("model_main"),
        model_lite=profile.get("model_lite"),
        model_relevance=profile.get("model_relevance"),
        organization=profile.get("organization"),
    )
    # save_llm_settings skips None values (preserve existing). Clear base_url
    # when the target profile has none (e.g. Gemini).
    if profile.get("base_url") is None:
        save_app_setting("llm_base_url", None)

    logger.info(f"Quick-switching LLM to profile '{req.label}' ({provider})")

    swap_result = await hot_swap_llm_client()
    if not swap_result["success"]:
        return ProviderSwitchResponse(
            success=False, label=req.label, provider=provider,
            error=swap_result.get("error"),
        )

    settings = get_llm_settings()
    return ProviderSwitchResponse(
        success=True, label=req.label, provider=settings["provider"],
        model_main=settings["model_main"],
        client_type=swap_result.get("client_type"),
    )


@router.get("/llm/providers", response_model=AvailableProvidersResponse)
async def list_available_providers() -> AvailableProvidersResponse:
    """List all LLM providers available for quick-switching via the chat toggle.

    Providers come from two sources:
    1. .env-detected: GEMINI_API_KEY, OPENAI_API_KEY, OPENROUTER_API_KEY
    2. DB-saved profiles: from previous PUT /v1/settings/llm calls

    The current active provider is determined by matching the active DB config
    against known profiles.
    """
    env_settings = get_settings()
    current_settings = get_llm_settings()
    saved_profiles = _read_all_profiles()

    # Build a merged dict: slug → profile, from .env + DB profiles.
    # DB profiles take precedence (they have the user's chosen model/key).
    all_profiles = {}
    for p in _detect_env_providers(env_settings):
        all_profiles[p["slug"]] = p
    for slug, p in saved_profiles.items():
        all_profiles[slug] = {**p, "slug": slug}

    # Determine current active profile slug by matching DB settings
    cur_slug = None
    if current_settings["provider"] == "gemini":
        cur_slug = "gemini"
    elif current_settings["base_url"]:
        cur_slug = _slug(_label_for_openai(current_settings["base_url"]))

    available = []
    for slug, p in all_profiles.items():
        if p.get("provider") == "gemini":
            label = p.get("label") or "Gemini"
        else:
            label = p.get("label") or _label_for_openai(p.get("base_url") or "")
        available.append(AvailableProvider(
            slug=slug,
            label=label,
            provider=p.get("provider", "openai_compatible"),
            model=p.get("model_main") or "unknown",
            has_api_key=bool(p.get("api_key")),
        ))

    # Sort: current first, then alphabetical
    available.sort(key=lambda a: (a.slug != cur_slug, a.slug))

    return AvailableProvidersResponse(current=cur_slug, available=available)


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

    # Validate the URL is a local Ollama instance before making any request.
    # This prevents SSRF — without validation an attacker could point the
    # server at internal services (e.g. cloud metadata endpoints).
    try:
        validated_url = _validate_ollama_url(base_url)
    except HTTPException:
        # Not a valid local Ollama URL — fall through to the empty-list
        # response for non-Ollama providers (user enters model name manually).
        return LLMModelsResponse(models=[])

    try:
        return await _list_ollama_models(validated_url)
    except Exception as e:
        logger.error(f"Failed to list Ollama models: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch models from Ollama: {e}")


class LLMTestRequest(BaseModel):
    """Request body for POST /v1/settings/llm/test.

    If api_key is None, the existing saved key is used (so users can re-test
    without re-entering the key).
    """
    provider: str = Field(..., description="Provider: 'gemini' or 'openai_compatible'")
    api_key: Optional[str] = Field(None, description="API key to test. If None, uses the existing saved key.")
    base_url: Optional[str] = Field(None, description="Base URL for OpenAI-compatible providers")
    model_main: Optional[str] = Field(None, description="Model name to test")


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
