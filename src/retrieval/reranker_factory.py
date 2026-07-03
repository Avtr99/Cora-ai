"""Pluggable reranker abstraction.

Provides a uniform ``rerank`` interface so the retriever is not locked to
Voyage AI.  Supported providers (selected via ``RERANK_PROVIDER`` setting):

    - ``voyage``  — Voyage rerank-2.5 (default, cloud API)
    - ``cohere``  — Cohere rerank-3.5 (cloud API)
    - ``none``    — Skip reranking, preserve dense retrieval order (local/offline)

When ``RERANK_PROVIDER=none``, the retriever falls back to dense cosine
scores — no external API call is needed, which is useful for fully offline
DGP-aligned deployments.
"""

import logging
from typing import List, Optional, Tuple

from ..config import get_settings

logger = logging.getLogger(__name__)


class Reranker:
    """Abstract reranker — call ``rerank()`` to reorder documents."""

    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: int,
    ) -> List[Tuple[int, float]]:
        """Rerank documents against the query.

        Args:
            query: The search query.
            documents: List of document text strings.
            top_k: Number of top results to return.

        Returns:
            List of ``(original_index, relevance_score)`` tuples sorted by
            relevance descending.  ``relevance_score`` is in [0.0, 1.0].
        """
        raise NotImplementedError


class VoyageReranker(Reranker):
    """Voyage AI reranker (rerank-2.5)."""

    def __init__(self, api_key: str, model: str = "rerank-2.5"):
        import voyageai

        self._client = voyageai.Client(api_key=api_key, max_retries=3)
        self._model = model

    def rerank(self, query: str, documents: List[str], top_k: int) -> List[Tuple[int, float]]:
        response = self._client.rerank(
            query=query,
            documents=documents,
            model=self._model,
            top_k=top_k,
        )
        results = []
        for r in response.results:
            score = min(max(r.relevance_score, 0.0), 1.0)
            results.append((r.index, score))
        return results


class CohereReranker(Reranker):
    """Cohere reranker (rerank-3.5)."""

    def __init__(self, api_key: str, model: str = "rerank-english-v3.0"):
        import cohere

        self._client = cohere.ClientV2(api_key=api_key)
        self._model = model

    def rerank(self, query: str, documents: List[str], top_k: int) -> List[Tuple[int, float]]:
        response = self._client.rerank(
            model=self._model,
            query=query,
            documents=documents,
            top_n=top_k,
        )
        results = []
        for r in response.results:
            score = min(max(r.relevance_score, 0.0), 1.0)
            results.append((r.index, score))
        return results


class NoopReranker(Reranker):
    """No-op reranker — preserves original dense retrieval order.

    Returns scores of 1.0 for all documents (dense scores are already
    handled by the caller).  Use when running fully offline or when no
    reranker API is configured.
    """

    def rerank(self, query: str, documents: List[str], top_k: int) -> List[Tuple[int, float]]:
        return [(i, 1.0) for i in range(min(top_k, len(documents)))]


def create_reranker() -> Optional[Reranker]:
    """Create a ``Reranker`` instance for the configured provider.

    Returns ``None`` if reranking is disabled (``RERANK_PROVIDER=none`` and
    the caller should use dense scores directly).

    Raises:
        ValueError: If the provider is unknown or credentials are missing.
        ImportError: If the provider's SDK is not installed.
    """
    settings = get_settings()
    provider = settings.RERANK_PROVIDER.lower()

    if provider == "none":
        logger.info("Reranking disabled (RERANK_PROVIDER=none) — using dense scores")
        return None
    elif provider == "voyage":
        if not settings.VOYAGE_API_KEY:
            raise ValueError("VOYAGE_API_KEY is required when RERANK_PROVIDER=voyage")
        model = settings.RERANK_MODEL or "rerank-2.5"
        logger.info("Using Voyage reranker (model=%s)", model)
        return VoyageReranker(api_key=settings.VOYAGE_API_KEY, model=model)
    elif provider == "cohere":
        if not settings.COHERE_API_KEY:
            raise ValueError("COHERE_API_KEY is required when RERANK_PROVIDER=cohere")
        model = settings.RERANK_MODEL or "rerank-english-v3.0"
        logger.info("Using Cohere reranker (model=%s)", model)
        return CohereReranker(api_key=settings.COHERE_API_KEY, model=model)
    else:
        raise ValueError(
            f"Unknown RERANK_PROVIDER: '{provider}'. "
            f"Supported: voyage, cohere, none"
        )
