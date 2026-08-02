"""Embedding provider settings routes."""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from loguru import logger

from ...config import get_settings, reload_settings
from ...db.app_settings import save_app_settings
from ...utils.cache import invalidate_query_cache_for_config_change
from .helpers import embedding_has_api_key

router = APIRouter()


class EmbeddingSettingsResponse(BaseModel):
    """Response model for GET /v1/settings/embeddings."""
    provider: str = Field(..., description="Embedding provider: voyage, cohere, ollama, openai")
    model: str = Field(..., description="Embedding model name")
    dim: int = Field(..., description="Embedding dimension (must match Qdrant collection)")
    has_api_key: bool = Field(False, description="Whether the required API key is set")
    ollama_base_url: Optional[str] = Field(None, description="Ollama base URL (for ollama provider)")
    is_configured: bool = Field(..., description="Whether embeddings are ready to use")


class EmbeddingSettingsUpdate(BaseModel):
    """Request model for PUT /v1/settings/embeddings."""
    provider: str = Field(..., description="Embedding provider: voyage, cohere, ollama, openai")
    model: Optional[str] = Field(None, description="Embedding model name")
    dim: Optional[int] = Field(None, description="Embedding dimension")
    api_key: Optional[str] = Field(None, description="API key. If None, existing key is preserved.")
    ollama_base_url: Optional[str] = Field(None, description="Ollama base URL (for ollama provider)")


@router.get("/embeddings", response_model=EmbeddingSettingsResponse)
async def get_embedding_config() -> EmbeddingSettingsResponse:
    """Get current embedding provider configuration."""
    settings = get_settings()
    provider = settings.EMBEDDING_PROVIDER.lower()

    has_key = embedding_has_api_key(settings)

    return EmbeddingSettingsResponse(
        provider=provider,
        model=settings.EMBEDDING_MODEL,
        dim=settings.EMBEDDING_DIM,
        has_api_key=has_key,
        ollama_base_url=settings.OLLAMA_BASE_URL if provider == "ollama" else None,
        is_configured=has_key,
    )


@router.put("/embeddings", response_model=EmbeddingSettingsResponse)
async def update_embedding_config(update: EmbeddingSettingsUpdate) -> EmbeddingSettingsResponse:
    """Update embedding provider configuration.

    Saves to the app_settings table and reloads the Settings singleton so
    the new values take effect immediately (for new requests).
    """
    valid_providers = ("voyage", "cohere", "ollama", "openai")
    if update.provider.lower() not in valid_providers:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider '{update.provider}'. Must be one of: {', '.join(valid_providers)}"
        )

    provider = update.provider.lower()

    # Build the full settings dict and write it in a single transaction so a
    # crash mid-save cannot leave a partial config (provider written, key not).
    defaults = {
        "voyage": "voyage-4-lite",
        "cohere": "embed-english-v3",
        "ollama": "bge-large-en-v1.5",
        "openai": "text-embedding-3-small",
    }
    model = update.model or defaults.get(provider, "")

    default_dims = {"voyage": 1024, "cohere": 1024, "ollama": 1024, "openai": 1024}
    dim = update.dim or default_dims.get(provider, 1024)

    settings_dict = {
        "embedding_provider": provider,
        "embedding_model": model,
        "embedding_dim": str(dim),
    }

    # API key — scoped per provider so the reranker route (which has its own
    # reranker_*_api_key keys) can never overwrite this one. An empty string
    # clears the key; None means "not sent, preserve existing" (skip the write).
    if update.api_key is not None:
        if provider == "voyage":
            settings_dict["embedding_voyage_api_key"] = update.api_key or None
        elif provider == "cohere":
            settings_dict["embedding_cohere_api_key"] = update.api_key or None
        elif provider == "openai":
            settings_dict["embedding_openai_api_key"] = update.api_key or None
        # Ollama doesn't need a key

    if update.ollama_base_url is not None:
        settings_dict["ollama_base_url"] = update.ollama_base_url or None

    save_app_settings(settings_dict)

    # Reload settings so the new values take effect
    reload_settings()
    # Invalidate cached answers from the old embedding stack.
    await invalidate_query_cache_for_config_change()
    logger.info(f"Embedding settings updated: provider={provider}, model={model}, dim={dim} (cache invalidated)")

    return await get_embedding_config()
