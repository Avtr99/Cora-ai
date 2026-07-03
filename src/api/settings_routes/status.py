"""Full configuration status route."""

from typing import Optional, List
from fastapi import APIRouter
from pydantic import BaseModel, Field

from ...config import get_settings
from ...query_processing.llm_factory import (
    get_llm_settings,
    is_llm_configured,
)

router = APIRouter()


class ProviderStatus(BaseModel):
    """Status of a single provider."""
    provider: str = Field(..., description="Provider name (e.g. 'gemini', 'voyage', 'none')")
    has_api_key: bool = Field(False, description="Whether the required API key is set")
    model: Optional[str] = Field(None, description="Configured model name")
    is_configured: bool = Field(..., description="Whether this provider is ready to use")
    warning: Optional[str] = Field(None, description="Warning message if misconfigured")


class ConfigStatusResponse(BaseModel):
    """Full configuration status with validation warnings."""
    ready: bool = Field(..., description="True if all required providers are configured and compatible")
    llm: ProviderStatus = Field(..., description="LLM provider status")
    embeddings: ProviderStatus = Field(..., description="Embedding provider status")
    reranker: ProviderStatus = Field(..., description="Reranker provider status")
    search: ProviderStatus = Field(..., description="Web search provider status")
    qdrant: Optional[dict] = Field(None, description="Qdrant collection info (if reachable)")
    warnings: List[str] = Field(default_factory=list, description="All validation warnings")
    chat_ready: bool = Field(..., description="True when the chat can answer grounded questions: LLM is configured and either the KB has documents or web search is enabled")
    kb_ready: bool = Field(..., description="True when the Qdrant knowledge base has indexed documents")
    search_ready: bool = Field(..., description="True when a web search provider other than 'none' is configured")


@router.get("/status", response_model=ConfigStatusResponse)
async def get_config_status() -> ConfigStatusResponse:
    """Get full configuration status with validation warnings.

    Checks all providers (LLM, embeddings, reranker, search) and verifies
    that the configured embedding dimension matches the Qdrant collection
    vector size (if the collection exists).
    """
    settings = get_settings()
    warnings: List[str] = []

    # --- LLM ---
    llm_settings = get_llm_settings()
    llm_configured = is_llm_configured()
    llm_warning = None
    if not llm_configured:
        llm_warning = "No LLM provider configured. Set up via /setup or .env."
        warnings.append(llm_warning)

    # Determine LLM API key presence
    llm_has_key = llm_settings["api_key"] is not None
    if llm_settings["provider"] == "openai_compatible":
        # Ollama doesn't need a key — check base_url for localhost:11434
        base_url = llm_settings.get("base_url") or ""
        if "localhost:11434" in base_url or "127.0.0.1:11434" in base_url:
            llm_has_key = True  # Ollama — no key needed

    llm_status = ProviderStatus(
        provider=llm_settings["provider"] or "unset",
        has_api_key=llm_has_key,
        model=llm_settings["model_main"],
        is_configured=llm_configured,
        warning=llm_warning,
    )

    # --- Embeddings ---
    emb_provider = settings.EMBEDDING_PROVIDER.lower()
    emb_has_key = False
    emb_warning = None

    if emb_provider == "voyage":
        emb_has_key = bool(settings.VOYAGE_API_KEY)
    elif emb_provider == "cohere":
        emb_has_key = bool(settings.COHERE_API_KEY)
    elif emb_provider == "openai":
        emb_has_key = bool(getattr(settings, "OPENAI_API_KEY", None))
    elif emb_provider == "ollama":
        emb_has_key = True  # No key needed

    emb_configured = emb_has_key
    if not emb_has_key:
        emb_warning = f"Embedding provider '{emb_provider}' requires an API key. Set it in .env."
        warnings.append(emb_warning)

    emb_status = ProviderStatus(
        provider=emb_provider,
        has_api_key=emb_has_key,
        model=settings.EMBEDDING_MODEL,
        is_configured=emb_configured,
        warning=emb_warning,
    )

    # --- Reranker ---
    rerank_provider = settings.RERANK_PROVIDER.lower()
    rerank_has_key = False
    rerank_warning = None

    if rerank_provider == "none":
        rerank_has_key = True  # No key needed — reranking disabled
        rerank_configured = True
    elif rerank_provider == "voyage":
        rerank_has_key = bool(settings.VOYAGE_API_KEY)
        rerank_configured = rerank_has_key
    elif rerank_provider == "cohere":
        rerank_has_key = bool(settings.COHERE_API_KEY)
        rerank_configured = rerank_has_key
    else:
        rerank_configured = False
        rerank_warning = f"Unknown reranker provider '{rerank_provider}'. Use voyage, cohere, or none."
        warnings.append(rerank_warning)

    if rerank_provider in ("voyage", "cohere") and not rerank_has_key:
        rerank_warning = f"Reranker provider '{rerank_provider}' requires an API key. Set RERANK_PROVIDER=none to disable."
        warnings.append(rerank_warning)

    rerank_status = ProviderStatus(
        provider=rerank_provider,
        has_api_key=rerank_has_key,
        model=settings.RERANK_MODEL if rerank_provider != "none" else None,
        is_configured=rerank_configured,
        warning=rerank_warning,
    )

    # --- Search ---
    search_provider = settings.SEARCH_PROVIDER.lower()
    search_has_key = False
    search_warning = None

    if search_provider == "none":
        search_has_key = True
        search_configured = True
    elif search_provider == "tavily":
        search_has_key = bool(settings.TAVILY_API_KEY)
        search_configured = search_has_key
        if not search_has_key:
            search_warning = "Search provider 'tavily' requires TAVILY_API_KEY. Set SEARCH_PROVIDER=none to disable."
            warnings.append(search_warning)
    else:
        search_configured = False
        search_warning = f"Unknown search provider '{search_provider}'. Use tavily or none."
        warnings.append(search_warning)

    search_status = ProviderStatus(
        provider=search_provider,
        has_api_key=search_has_key,
        model=None,
        is_configured=search_configured,
        warning=search_warning,
    )

    # --- Qdrant dimension check ---
    qdrant_info = None
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(url=settings.QDRANT_URL, timeout=5)
        try:
            collection_name = getattr(settings, "QDRANT_COLLECTION", "cora")
            # Try both common collection names
            for name in [collection_name, "cora_dense_only"]:
                try:
                    info = client.get_collection(name)
                    vector_config = info.config.params.vectors
                    # VectorParams or dict of VectorParams
                    if hasattr(vector_config, "size"):
                        qdrant_dim = vector_config.size
                    elif isinstance(vector_config, dict):
                        first = next(iter(vector_config.values()))
                        qdrant_dim = getattr(first, "size", None)
                    else:
                        qdrant_dim = None

                    qdrant_info = {
                        "collection": name,
                        "vector_dim": qdrant_dim,
                        "points_count": info.points_count,
                    }

                    if qdrant_dim is not None and qdrant_dim != settings.EMBEDDING_DIM:
                        dim_warning = (
                            f"Embedding dimension mismatch: EMBEDDING_DIM={settings.EMBEDDING_DIM} "
                            f"but Qdrant collection '{name}' has vector size {qdrant_dim}. "
                            f"Re-ingest documents or update EMBEDDING_DIM to {qdrant_dim}."
                        )
                        warnings.append(dim_warning)
                    break
                except Exception:
                    continue
        finally:
            client.close()
    except Exception as e:
        qdrant_info = {"error": str(e)}
        warnings.append(f"Could not connect to Qdrant at {settings.QDRANT_URL}: {e}")

    # --- Overall readiness ---
    ready = llm_configured and emb_configured and rerank_configured and search_configured
    # Qdrant dimension mismatch is a warning, not a hard failure (collection may not exist yet)

    # --- Chat readiness ---
    # KB is ready when Qdrant is reachable and has at least one indexed point.
    kb_points = (qdrant_info or {}).get("points_count", 0)
    kb_ready = isinstance(kb_points, int) and kb_points > 0

    # Search is ready when a real provider (not "none") is configured.
    search_ready = search_provider != "none" and search_configured
    # Chat can answer grounded questions only when the LLM is configured and there
    # is at least one answer source (KB or web search).
    chat_ready = llm_configured and (kb_ready or search_ready)

    return ConfigStatusResponse(
        ready=ready,
        llm=llm_status,
        embeddings=emb_status,
        reranker=rerank_status,
        search=search_status,
        qdrant=qdrant_info,
        warnings=warnings,
        chat_ready=chat_ready,
        kb_ready=kb_ready,
        search_ready=search_ready,
    )
