"""Reranker provider settings routes."""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from loguru import logger

from ...config import get_settings, reload_settings
from ...db.app_settings import save_app_settings
from ...utils.cache import invalidate_query_cache_for_config_change
from .helpers import reranker_has_api_key

router = APIRouter()


class RerankerSettingsResponse(BaseModel):
    """Response model for GET /v1/settings/reranker."""
    provider: str = Field(..., description="Reranker provider: voyage, cohere, or none")
    model: Optional[str] = Field(None, description="Reranker model name")
    has_api_key: bool = Field(False, description="Whether the required API key is set")
    is_configured: bool = Field(..., description="Whether reranker is ready (or disabled)")


class RerankerSettingsUpdate(BaseModel):
    """Request model for PUT /v1/settings/reranker."""
    provider: str = Field(..., description="Provider: voyage, cohere, or none")
    model: Optional[str] = Field(None, description="Model name (optional)")
    api_key: Optional[str] = Field(None, description="API key. If None, existing key is preserved.")


@router.get("/reranker", response_model=RerankerSettingsResponse)
async def get_reranker_config() -> RerankerSettingsResponse:
    """Get current reranker provider configuration."""
    settings = get_settings()
    provider = settings.RERANK_PROVIDER.lower()

    has_key = reranker_has_api_key(settings)

    return RerankerSettingsResponse(
        provider=provider,
        model=settings.RERANK_MODEL if provider != "none" else None,
        has_api_key=has_key,
        is_configured=has_key,
    )


@router.put("/reranker", response_model=RerankerSettingsResponse)
async def update_reranker_config(update: RerankerSettingsUpdate) -> RerankerSettingsResponse:
    """Update reranker provider configuration."""
    valid_providers = ("voyage", "cohere", "none")
    if update.provider.lower() not in valid_providers:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider '{update.provider}'. Must be one of: {', '.join(valid_providers)}"
        )

    provider = update.provider.lower()

    # Single transactional write so a crash cannot leave a partial config.
    settings_dict = {"rerank_provider": provider}

    if update.model is not None:
        settings_dict["rerank_model"] = update.model or None

    # API key — scoped per provider so the embeddings route (which has its
    # own embedding_*_api_key keys) can never overwrite this one. Empty string
    # clears; None means "not sent, preserve existing" (skip the write).
    if update.api_key is not None:
        if provider == "voyage":
            settings_dict["reranker_voyage_api_key"] = update.api_key or None
        elif provider == "cohere":
            settings_dict["reranker_cohere_api_key"] = update.api_key or None

    save_app_settings(settings_dict)

    reload_settings()
    # Invalidate cached answers from the old reranker stack.
    await invalidate_query_cache_for_config_change()
    logger.info(f"Reranker settings updated: provider={provider} (cache invalidated)")

    return await get_reranker_config()
