"""LLM provider profile routes (switch / list)."""

from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from loguru import logger

from ...config import get_settings, reload_settings
from ...query_processing.llm_factory import get_llm_settings
from ...db.llm_profile_manager import (
    _save_profile,
    get_profile_label,
    get_profile_slug,
    build_available_providers,
    resolve_profile_for_switch,
)
from ..lifespan import hot_swap_llm_client
from ...utils.cache import invalidate_query_cache_for_config_change
from .llm_service import _write_llm_settings, _validate_llm_models

router = APIRouter()


class ProviderSwitchRequest(BaseModel):
    """Request model for POST /v1/settings/llm/switch.

    Used by the chat provider toggle to instantly switch between providers.
    Takes a profile slug (e.g. "gemini", "openai", "openrouter") -- not a
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


@router.post("/llm/switch", response_model=ProviderSwitchResponse)
async def switch_llm_provider(req: ProviderSwitchRequest) -> ProviderSwitchResponse:
    """Quick-switch the active LLM provider by profile label.

    Switches to a provider profile whose API key is already configured (in
    .env or saved via PUT /v1/settings/llm). The LLM client and orchestrator are hot-swapped
    in-place -- no restart needed.

    The current config is saved as a profile before switching, so switching back
    restores it exactly.

    For initial provider setup (entering new API keys), use PUT /v1/settings/llm.
    """
    # ponytail: no lock -- local-first single-user app, concurrent switches are
    # not a real concern. If two switches race, the last one wins.
    env_settings = get_settings()
    current_settings = get_llm_settings()

    # Save current config as a profile so switching back restores it
    if current_settings["provider"]:
        label = get_profile_label(current_settings["provider"], current_settings["base_url"])
        _save_profile(
            get_profile_slug(label), current_settings["provider"],
            current_settings["api_key"], current_settings["base_url"],
            current_settings["model_main"], current_settings["model_lite"],
            current_settings["model_relevance"], current_settings["organization"],
        )

    # Find the target profile: saved DB profile first, then .env-detected
    profile = resolve_profile_for_switch(req.label, env_settings)

    if not profile:
        raise HTTPException(
            status_code=400,
            detail=f"No profile found for '{req.label}'. Configure it via Settings first."
        )

    provider = profile["provider"]
    new_settings = dict(current_settings)
    new_settings["provider"] = provider
    for field in ("api_key", "base_url", "model_main", "model_lite", "model_relevance", "organization"):
        new_settings[field] = profile.get(field)

    # Validate model names before writing — a corrupted profile (e.g. a Gemini
    # model name saved under an OpenRouter profile) would cause 400 errors on
    # the next query. Better to reject the switch than to apply a broken config.
    _validate_llm_models(
        provider,
        new_settings.get("model_main"),
        new_settings.get("model_lite"),
        new_settings.get("model_relevance"),
    )

    _write_llm_settings(new_settings)

    # Bump the config-version observability counter.
    reload_settings()

    logger.info(f"Quick-switching LLM to profile '{req.label}' ({provider})")

    swap_result = await hot_swap_llm_client()
    if not swap_result["success"]:
        logger.warning(
            f"LLM switch to '{req.label}' failed: {swap_result.get('error')}. "
            "Rolling back to previous configuration."
        )
        _write_llm_settings(current_settings)
        reload_settings()
        return ProviderSwitchResponse(
            success=False, label=req.label, provider=provider,
            error=swap_result.get("error"),
        )

    # Invalidate cached answers from the previous LLM model.
    await invalidate_query_cache_for_config_change()
    logger.info("LLM provider switched -- query cache invalidated")

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

    cur_slug, available = build_available_providers(current_settings, env_settings)

    return AvailableProvidersResponse(
        current=cur_slug,
        available=[AvailableProvider(**a) for a in available],
    )
