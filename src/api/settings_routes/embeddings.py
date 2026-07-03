"""Embedding provider settings routes."""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from loguru import logger

from ...config import get_settings, reload_settings
from ...db.app_settings import save_app_setting

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

    has_key = False
    if provider == "voyage":
        has_key = bool(settings.VOYAGE_API_KEY)
    elif provider == "cohere":
        has_key = bool(settings.COHERE_API_KEY)
    elif provider == "openai":
        has_key = bool(getattr(settings, "OPENAI_API_KEY", None))
    elif provider == "ollama":
        has_key = True  # No key needed

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

    # Save provider
    save_app_setting("embedding_provider", provider)

    # Save model (use default if not provided)
    defaults = {
        "voyage": "voyage-4-lite",
        "cohere": "embed-english-v3",
        "ollama": "bge-large-en-v1.5",
        "openai": "text-embedding-3-small",
    }
    model = update.model or defaults.get(provider, "")
    save_app_setting("embedding_model", model)

    # Save dimension (use default if not provided)
    default_dims = {"voyage": 1024, "cohere": 1024, "ollama": 1024, "openai": 1024}
    dim = update.dim or default_dims.get(provider, 1024)
    save_app_setting("embedding_dim", str(dim))

    # Save API key to the appropriate key
    if update.api_key is not None:
        if provider == "voyage":
            save_app_setting("voyage_api_key", update.api_key)
        elif provider == "cohere":
            save_app_setting("cohere_api_key", update.api_key)
        elif provider == "openai":
            save_app_setting("openai_api_key", update.api_key)
        # Ollama doesn't need a key

    # Save Ollama base URL if provided
    if update.ollama_base_url is not None:
        save_app_setting("ollama_base_url", update.ollama_base_url)

    # Reload settings so the new values take effect
    reload_settings()
    logger.info(f"Embedding settings updated: provider={provider}, model={model}, dim={dim}")

    return await get_embedding_config()
