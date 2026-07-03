"""Web search provider settings routes."""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from loguru import logger

from ...config import get_settings, reload_settings
from ...db.app_settings import save_app_setting

router = APIRouter()


class SearchSettingsResponse(BaseModel):
    """Response model for GET /v1/settings/search."""
    provider: str = Field(..., description="Search provider: tavily or none")
    has_api_key: bool = Field(False, description="Whether the required API key is set")
    is_configured: bool = Field(..., description="Whether search is ready to use (or disabled)")


class SearchSettingsUpdate(BaseModel):
    """Request model for PUT /v1/settings/search."""
    provider: str = Field(..., description="Provider: tavily or none")
    api_key: Optional[str] = Field(None, description="API key. If None, existing key is preserved.")


@router.get("/search", response_model=SearchSettingsResponse)
async def get_search_config() -> SearchSettingsResponse:
    """Get current web search provider configuration."""
    settings = get_settings()
    provider = settings.SEARCH_PROVIDER.lower()

    has_key = False
    if provider == "none":
        has_key = True  # Disabled — no key needed
    elif provider == "tavily":
        has_key = bool(settings.TAVILY_API_KEY)

    return SearchSettingsResponse(
        provider=provider,
        has_api_key=has_key,
        is_configured=has_key,
    )


@router.put("/search", response_model=SearchSettingsResponse)
async def update_search_config(update: SearchSettingsUpdate) -> SearchSettingsResponse:
    """Update web search provider configuration."""
    valid_providers = ("tavily", "none")
    if update.provider.lower() not in valid_providers:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider '{update.provider}'. Must be one of: {', '.join(valid_providers)}"
        )

    provider = update.provider.lower()
    save_app_setting("search_provider", provider)

    if update.api_key is not None and provider == "tavily":
        save_app_setting("tavily_api_key", update.api_key)

    # Reload settings
    reload_settings()
    logger.info(f"Search settings updated: provider={provider}")

    return await get_search_config()
