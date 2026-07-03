"""Pluggable embedding provider factory.

Returns a LangChain ``Embeddings`` object for the configured provider so the
retriever and memory modules stay provider-agnostic.

Supported providers (selected via ``EMBEDDING_PROVIDER`` setting):
    - ``voyage``  — Voyage AI (voyage-4-lite, 1024d)  [default]
    - ``cohere``  — Cohere (embed-english-v3, 1024d)
    - ``ollama``  — Local Ollama server (bge-large-en-v1.5 1024d, nomic-embed-text 768d, …)
    - ``openai``  — OpenAI (text-embedding-3-small 1536d, or 1024d via ``dimensions`` param)

Dimension compatibility:
    The Qdrant collection is created with a fixed vector size (``EMBEDDING_DIM``).
    Switching providers requires re-ingesting into a new collection if the
    dimension differs.  For 1024d compatibility with the default collection:
        - voyage:  voyage-4-lite / voyage-3.5          (native 1024d)
        - cohere:  embed-english-v3                    (native 1024d)
        - ollama:  bge-large-en-v1.5 / mxbai-embed-large  (native 1024d)
        - openai:  text-embedding-3-small with dimensions=1024  (truncated via API)

    For Ollama models with a different native dimension (e.g. nomic-embed-text
    at 768d), you MUST set ``EMBEDDING_DIM`` to match and create a new Qdrant
    collection — a dimension mismatch will cause Qdrant to reject queries at
    runtime.  The factory logs a warning when the configured ``EMBEDDING_DIM``
    does not match the provider's known native dimension.
"""

import logging
from typing import Any, Dict

from ..config import get_settings

logger = logging.getLogger(__name__)

# Known native dimensions for common models.
# Used to warn the user if EMBEDDING_DIM doesn't match — prevents silent
# Qdrant dimension-mismatch errors at query time.
_KNOWN_DIMS: Dict[str, int] = {
    # Voyage
    "voyage-4-lite": 1024,
    "voyage-4-large": 1024,
    "voyage-3.5": 1024,
    "voyage-3-lite": 512,
    "voyage-3": 1024,
    "voyage-large-2": 1536,
    # Cohere
    "embed-english-v3": 1024,
    "embed-english-light-v3": 384,
    "embed-multilingual-v3": 1024,
    "embed-multilingual-light-v3": 384,
    # Ollama (popular open-source models)
    "bge-large-en-v1.5": 1024,
    "bge-base-en-v1.5": 768,
    "mxbai-embed-large": 1024,
    "nomic-embed-text": 768,
    "all-MiniLM-L6-v2": 384,
    # OpenAI
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


def _check_dim_compatibility(model: str, configured_dim: int, provider: str) -> None:
    """Warn if the configured dimension doesn't match the model's native dimension.

    For OpenAI text-embedding-3 models, the ``dimensions`` API parameter allows
    truncation, so a mismatch is expected and NOT warned about (the factory
    passes ``dimensions=configured_dim`` to the API).
    """
    native_dim = _KNOWN_DIMS.get(model)
    if native_dim is None:
        logger.debug(
            "Unknown native dimension for model '%s' — skipping dim check. "
            "Ensure EMBEDDING_DIM=%d matches the Qdrant collection.",
            model, configured_dim,
        )
        return

    if native_dim == configured_dim:
        return

    # OpenAI text-embedding-3 supports dimension truncation via API parameter
    if provider == "openai" and model.startswith("text-embedding-3"):
        logger.info(
            "OpenAI model '%s' native dim=%d, configured EMBEDDING_DIM=%d "
            "(will request truncated dimensions via API).",
            model, native_dim, configured_dim,
        )
        return

    logger.warning(
        "DIMENSION MISMATCH: model '%s' has native dim=%d but EMBEDDING_DIM=%d. "
        "If the Qdrant collection was created with a different vector size, "
        "queries will fail. To fix: either (a) set EMBEDDING_DIM=%d and "
        "re-create the Qdrant collection, or (b) use a model with native %d-dim vectors.",
        model, native_dim, configured_dim, native_dim, configured_dim,
    )


def create_embeddings() -> Any:
    """Create and return a LangChain ``Embeddings`` instance for the configured provider.

    The provider is selected via ``EMBEDDING_PROVIDER`` in settings.  Each
    provider's LangChain integration is imported lazily so only the active
    provider's package needs to be installed.

    Returns:
        A LangChain ``Embeddings`` object (e.g. ``VoyageAIEmbeddings``,
        ``CohereEmbeddings``, ``OllamaEmbeddings``, ``OpenAIEmbeddings``).

    Raises:
        ValueError: If the provider is unknown or required credentials are missing.
        ImportError: If the provider's LangChain integration package is not installed.
    """
    settings = get_settings()
    provider = settings.EMBEDDING_PROVIDER.lower()

    if provider == "voyage":
        return _create_voyage_embeddings(settings)
    elif provider == "cohere":
        return _create_cohere_embeddings(settings)
    elif provider == "ollama":
        return _create_ollama_embeddings(settings)
    elif provider == "openai":
        return _create_openai_embeddings(settings)
    else:
        raise ValueError(
            f"Unknown EMBEDDING_PROVIDER: '{provider}'. "
            f"Supported: voyage, cohere, ollama, openai"
        )


def _create_voyage_embeddings(settings) -> Any:
    """Voyage AI embeddings (default, 1024d with voyage-4-lite)."""
    if not settings.VOYAGE_API_KEY:
        raise ValueError("VOYAGE_API_KEY is required when EMBEDDING_PROVIDER=voyage")

    from langchain_voyageai import VoyageAIEmbeddings

    model = settings.EMBEDDING_MODEL or "voyage-4-lite"
    _check_dim_compatibility(model, settings.EMBEDDING_DIM, "voyage")
    logger.info("Using Voyage AI embeddings (model=%s, dim=%d)", model, settings.EMBEDDING_DIM)
    return VoyageAIEmbeddings(
        model=model,
        voyage_api_key=settings.VOYAGE_API_KEY,
    )


def _create_cohere_embeddings(settings) -> Any:
    """Cohere embeddings (1024d with embed-english-v3 — drop-in compatible)."""
    if not settings.COHERE_API_KEY:
        raise ValueError("COHERE_API_KEY is required when EMBEDDING_PROVIDER=cohere")

    from langchain_cohere import CohereEmbeddings

    model = settings.EMBEDDING_MODEL or "embed-english-v3"
    _check_dim_compatibility(model, settings.EMBEDDING_DIM, "cohere")
    logger.info("Using Cohere embeddings (model=%s, dim=%d)", model, settings.EMBEDDING_DIM)
    return CohereEmbeddings(
        model=model,
        cohere_api_key=settings.COHERE_API_KEY,
    )


def _create_ollama_embeddings(settings) -> Any:
    """Local Ollama embeddings (fully offline, DGP-aligned).

    Requires a running Ollama server with the model pulled:
        ollama pull bge-large-en-v1.5   # 1024d — compatible with existing collection
        ollama pull nomic-embed-text    # 768d — requires new collection with EMBEDDING_DIM=768
    """
    from langchain_ollama import OllamaEmbeddings

    model = settings.EMBEDDING_MODEL or "bge-large-en-v1.5"
    base_url = settings.OLLAMA_BASE_URL or "http://localhost:11434"
    _check_dim_compatibility(model, settings.EMBEDDING_DIM, "ollama")
    logger.info("Using Ollama embeddings (model=%s, base_url=%s, dim=%d)",
                model, base_url, settings.EMBEDDING_DIM)
    return OllamaEmbeddings(
        model=model,
        base_url=base_url,
    )


def _create_openai_embeddings(settings) -> Any:
    """OpenAI embeddings (text-embedding-3-small with configurable dimensions).

    OpenAI's text-embedding-3 models support a ``dimensions`` parameter that
    truncates the output vector to the specified size.  This means you can
    use ``text-embedding-3-small`` with ``EMBEDDING_DIM=1024`` to match an
    existing 1024d Qdrant collection without re-ingesting.

    Ref: https://docs.langchain.com/oss/python/integrations/embeddings/openai
    """
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai")

    from langchain_openai import OpenAIEmbeddings

    model = settings.EMBEDDING_MODEL or "text-embedding-3-small"
    _check_dim_compatibility(model, settings.EMBEDDING_DIM, "openai")
    logger.info("Using OpenAI embeddings (model=%s, dim=%d)", model, settings.EMBEDDING_DIM)

    # text-embedding-3 models support the dimensions parameter for truncation.
    # Pass it only for those models — older models (ada-002) don't support it.
    kwargs: Dict[str, Any] = {
        "model": model,
        "api_key": settings.OPENAI_API_KEY,
    }
    if model.startswith("text-embedding-3"):
        kwargs["dimensions"] = settings.EMBEDDING_DIM

    return OpenAIEmbeddings(**kwargs)
