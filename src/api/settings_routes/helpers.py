"""Shared helpers for the settings route handlers.

Avoids duplicating the ``has_api_key`` branching between the individual
GET routes and the full ``/v1/settings/status`` route.
"""

from typing import Any


def embedding_has_api_key(settings: Any) -> bool:
    """Return True if the configured embedding provider has its required key.

    Reads the embedding-scoped key first, falling back to the shared .env key
    so an operator who set VOYAGE_API_KEY/COHERE_API_KEY/OPENAI_API_KEY in
    .env (and never used the Settings UI) is still considered configured.
    """
    provider = settings.EMBEDDING_PROVIDER.lower()
    if provider == "voyage":
        return bool(getattr(settings, "EMBEDDING_VOYAGE_API_KEY", None) or getattr(settings, "VOYAGE_API_KEY", None))
    elif provider == "cohere":
        return bool(getattr(settings, "EMBEDDING_COHERE_API_KEY", None) or getattr(settings, "COHERE_API_KEY", None))
    elif provider == "openai":
        return bool(getattr(settings, "EMBEDDING_OPENAI_API_KEY", None) or getattr(settings, "OPENAI_API_KEY", None))
    elif provider == "ollama":
        return True  # No API key needed
    return False


def reranker_has_api_key(settings: Any) -> bool:
    """Return True if the configured reranker has its required key (or is disabled).

    Reads the reranker-scoped key first, falling back to the shared .env key.
    """
    provider = settings.RERANK_PROVIDER.lower()
    if provider == "none":
        return True  # No API key needed — reranking is disabled
    elif provider == "voyage":
        return bool(getattr(settings, "RERANKER_VOYAGE_API_KEY", None) or getattr(settings, "VOYAGE_API_KEY", None))
    elif provider == "cohere":
        return bool(getattr(settings, "RERANKER_COHERE_API_KEY", None) or getattr(settings, "COHERE_API_KEY", None))
    return False
