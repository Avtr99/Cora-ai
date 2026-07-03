"""Reranker provider settings routes."""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from loguru import logger

from ...config import get_settings, reload_settings
from ...db.app_settings import save_app_setting

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

    has_key = False
    if provider == "none":
        has_key = True
    elif provider == "voyage":
        has_key = bool(settings.VOYAGE_API_KEY)
    elif provider == "cohere":
        has_key = bool(settings.COHERE_API_KEY)

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
    save_app_setting("rerank_provider", provider)

    if update.model is not None:
        save_app_setting("rerank_model", update.model)

    if update.api_key is not None:
        if provider == "voyage":
            save_app_setting("voyage_api_key", update.api_key)
        elif provider == "cohere":
            save_app_setting("cohere_api_key", update.api_key)

    reload_settings()
    logger.info(f"Reranker settings updated: provider={provider}")

    return await get_reranker_config()
