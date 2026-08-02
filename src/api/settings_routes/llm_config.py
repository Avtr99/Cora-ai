"""LLM provider configuration routes (GET/PUT /v1/settings/llm)."""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from loguru import logger

from ...config import get_settings, reload_settings
from ...query_processing.llm_factory import get_llm_settings, is_llm_configured
from ...query_processing.llm_config_models import LLMConfig
from ...db.llm_profile_manager import _save_profile, get_profile_label, get_profile_slug
from ..lifespan import hot_swap_llm_client
from ...utils.cache import invalidate_query_cache_for_config_change
from .llm_service import _write_llm_settings, _validate_llm_models

router = APIRouter()


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


@router.get("/llm", response_model=LLMSettingsResponse)
async def get_llm_config() -> LLMSettingsResponse:
    """Get current LLM provider configuration.

    **Security:** The API key is never returned. Only `has_api_key: true/false`.
    """
    settings = get_llm_settings()
    env_settings = get_settings()
    # When using .env fallback, model_main may be None -- fill in the
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
async def update_llm_config(update: LLMConfig) -> LLMSettingsResponse:
    """Update LLM provider configuration.

    If `api_key` is None, the existing key is preserved (not overwritten).
    If `api_key` is an empty string, the persisted key is deleted and the .env
    key is used as a fallback.

    The LLM client and RAG orchestrator are hot-swapped in-place after saving,
    so changes take effect immediately without a server restart.

    If the hot-swap fails (e.g. invalid API key or model), the new settings
    are rolled back to the previous configuration.
    """
    # FastAPI validates the request body against the discriminated union at
    # the boundary: unknown providers get 422, and provider-specific fields
    # (e.g. base_url on a Gemini config) are silently dropped via extra="ignore".
    # Cross-provider API key contamination is cleared by the field validator.

    # Only fields the user explicitly sent (exclude_unset=True). Fields that
    # don't exist on the provider-specific model (e.g. base_url on GeminiConfig)
    # are never present here — they were dropped during parsing.
    update_dict = update.model_dump(exclude_unset=True)

    old_settings = get_llm_settings()
    provider_changed = update.provider != old_settings["provider"]

    # Default base_url for OpenAI-compatible if not provided or empty.
    # Matches the old behavior: always default when base_url is falsy.
    if update.provider == "openai_compatible" and not update_dict.get("base_url"):
        update_dict["base_url"] = "https://api.openai.com/v1"

    # Validate model names before writing — a corrupted config (e.g. a Gemini
    # model name saved under an OpenRouter config) would cause 400 errors on
    # the next query. Better to reject than to apply a broken config.
    _validate_llm_models(
        update.provider,
        update_dict.get("model_main"),
        update_dict.get("model_lite"),
        update_dict.get("model_relevance"),
    )

    # Build the new settings from the old, replacing only fields the user
    # supplied. When switching providers, leave blank model fields as None so
    # the new provider's env defaults are used instead of stale values.
    merged = {**old_settings, **update_dict}

    # api_key: empty string means "delete the persisted key" (fall back to .env).
    if merged.get("api_key") == "":
        merged["api_key"] = None

    # When switching providers, clear stale model/org fields not explicitly set
    # so the new provider's env defaults are used instead of stale values.
    if provider_changed:
        for field in ("model_main", "model_lite", "model_relevance", "organization"):
            if field not in update_dict:
                merged[field] = None

    try:
        _write_llm_settings(merged)
        logger.info(f"LLM settings updated: provider={update.provider}")
    except Exception as e:
        logger.error(f"Failed to save LLM settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {e}")

    # Bump the config-version observability counter. This is a
    # no-op for the Settings singleton because LLM keys are outside DB overlay,
    # but it ensures any Settings UI change updates the version stamp.
    reload_settings()

    # Hot-swap the LLM client and orchestrator so changes take effect
    # immediately without a server restart.
    swap_result = await hot_swap_llm_client()
    if not swap_result["success"]:
        logger.warning(
            f"LLM settings saved but hot-swap failed: {swap_result.get('error')}. "
            "Rolling back to previous configuration."
        )
        _write_llm_settings(old_settings)
        reload_settings()
        raise HTTPException(
            status_code=400,
            detail=f"LLM configuration is invalid: {swap_result.get('error')}",
        )

    logger.info(f"LLM hot-swapped to {swap_result.get('client_type')} ({swap_result.get('model')})")

    # Save as a profile so the chat toggle can switch back to this config.
    # Use the post-write settings (already validated + sanitized by the union
    # inside _write_llm_settings) so a Gemini profile doesn't inherit a stale
    # OpenRouter/OpenAI URL.
    existing = get_llm_settings()
    label = get_profile_label(existing["provider"], existing["base_url"])
    # Resolve the actual api_key to save in the profile. When the user left the
    # field blank to preserve the existing key, read it from the active config
    # so the profile can be restored later.
    profile_api_key = update_dict.get("api_key") or existing["api_key"]
    _save_profile(
        get_profile_slug(label), existing["provider"], profile_api_key, existing["base_url"],
        existing["model_main"], existing["model_lite"],
        existing["model_relevance"], existing["organization"],
    )

    # Invalidate cached answers from the old LLM model. The LLM
    # answer-generation model is represented in the cache key via
    # config_revision, so a bump here changes every query-cache key.
    await invalidate_query_cache_for_config_change()
    logger.info("LLM settings updated -- query cache invalidated")

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
