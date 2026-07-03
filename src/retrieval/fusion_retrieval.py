"""
Multi-query fusion retrieval.

Runs dense search for the main query and each sub-query in parallel,
deduplicates candidates by page_content, then reranks the merged pool
against the main query. Falls back to standard retrieve() if fusion
produces no additional value.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from ..config import get_settings, get_collection_threshold
from .filter_builder import QdrantFilterBuilder
from .result_processor import apply_post_processing, format_results, rerank_results
from .retrieval_utils import ResultFilter

logger = logging.getLogger(__name__)


class FusionRetriever:
    """Handles multi-query fusion retrieval for complex queries.

    Encapsulates the parallel sub-query search, deduplication, reranking,
    and post-processing pipeline so the main retriever stays focused on
    single-query retrieval.
    """

    def __init__(
        self,
        vector_store,
        reranker,
        enable_reranking: bool,
        initial_candidates: int,
        filter_builder: QdrantFilterBuilder,
    ):
        """
        Args:
            vector_store: LangChain QdrantVectorStore instance.
            reranker: Pluggable Reranker instance (or None to skip reranking).
            enable_reranking: Whether reranking is enabled.
            initial_candidates: Candidate count for the main query.
            filter_builder: Shared QdrantFilterBuilder for filter validation.
        """
        self._vector_store = vector_store
        self._reranker = reranker
        self.enable_reranking = enable_reranking
        self.initial_candidates = initial_candidates
        self._filter_builder = filter_builder

    async def retrieve_with_fusion(
        self,
        query: str,
        sub_queries: List[str],
        where: Optional[Dict[str, Any]] = None,
        allow_unfiltered_fallback: bool = False,
        fallback_retrieve=None,
        original_query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve documents using multi-query fusion for complex queries.

        Args:
            query: Primary rewritten query
            sub_queries: Additional sub-queries from the query rewriter
            where: Optional metadata filters
            allow_unfiltered_fallback: Allow fallback to unfiltered search
            fallback_retrieve: Callable for standard retrieve() fallback
                when no sub_queries are provided.
            original_query: The un-rewritten user query, used for the lexical
                overlap guard (see ``LangChainRetriever.retrieve`` for rationale).

        Returns:
            Dict with keys: ids, documents, metadatas, distances, scores
        """
        if not sub_queries:
            if fallback_retrieve is not None:
                return await fallback_retrieve(
                    query,
                    where=where,
                    allow_unfiltered_fallback=allow_unfiltered_fallback,
                    original_query=original_query,
                )
            return {
                "ids": [], "documents": [], "metadatas": [],
                "distances": [], "scores": [],
            }

        settings = get_settings()
        n_results = getattr(settings, "ROUND1_K", 15)
        sub_candidates = getattr(settings, "SUBQUERY_CANDIDATES", 15)

        # Build qdrant filter once
        qdrant_filter = await self._build_fusion_filter(where, allow_unfiltered_fallback)

        # Run main query + sub-queries in parallel
        tasks = [self._dense_search(query, self.initial_candidates, qdrant_filter)]
        for sq in sub_queries[:3]:  # Cap at 3 sub-queries to limit latency
            sq_text = sq.strip()
            if sq_text and sq_text.lower() != query.lower():
                tasks.append(self._dense_search(sq_text, sub_candidates, qdrant_filter))

        all_results = await asyncio.gather(*tasks)

        # Merge and deduplicate by page_content (exact match)
        seen_content: Dict[str, int] = {}
        merged: List = []

        for batch in all_results:
            for doc, score in batch:
                content_key = doc.page_content
                if content_key not in seen_content:
                    seen_content[content_key] = len(merged)
                    merged.append((doc, score))

        if not merged:
            logger.info("Fusion retrieval: no candidates from any query")
            return {
                "ids": [], "documents": [], "metadatas": [],
                "distances": [], "scores": [],
            }

        logger.debug(
            "Fusion retrieval: %d unique candidates from %d queries",
            len(merged), len(tasks),
        )

        # Rerank merged pool against the main query
        if self.enable_reranking and self._reranker and len(merged) > 1:
            results = await asyncio.to_thread(
                rerank_results,
                self._reranker, query, merged, n_results,
            )
            # Drop off-topic docs below the rerank relevance floor. If nothing
            # clears it, results become empty -> orchestrator falls back to web.
            results = ResultFilter.apply_relevance_floor(
                results,
                float(get_collection_threshold(settings, "RERANK_SCORE_THRESHOLD") or 0.0)
            )
        else:
            results = format_results(merged[:n_results])

        # Pre-LLM lexical overlap guard (same as single-query path). Passes
        # both query forms so acronym expansion does not unfairly lower overlap.
        overlap_threshold = float(
            get_collection_threshold(settings, "QUERY_DOC_OVERLAP_THRESHOLD") or 0.0
        )
        if overlap_threshold > 0:
            results = ResultFilter.apply_overlap_guard(
                results, query, overlap_threshold,
                alternate_query=original_query,
            )

        # Apply post-processing pipeline
        max_per_source = int(max(getattr(settings, "MAX_CHUNKS_PER_SOURCE", 5), 0))
        return apply_post_processing(results, query, max_per_source)

    async def _build_fusion_filter(
        self,
        where: Optional[Dict[str, Any]],
        allow_unfiltered_fallback: bool,
    ):
        """Build a Qdrant filter for fusion retrieval, handling errors gracefully."""
        if not where:
            return None

        try:
            qdrant_filter, _ = await self._filter_builder.build_validated_filter(
                where, allow_unfiltered_fallback
            )
            return qdrant_filter
        except Exception as e:
            if allow_unfiltered_fallback:
                logger.warning(
                    "Filter build failed for fusion retrieval; allow_unfiltered_fallback=True, "
                    "continuing with unfiltered search. error=%s",
                    e,
                )
                return None
            logger.error(
                "Filter build failed for fusion retrieval and was blocked (fail-closed). "
                "allow_unfiltered_fallback=False error=%s",
                e,
            )
            raise

    async def _dense_search(self, query: str, k: int, qdrant_filter) -> List:
        """Run a single dense search, returning list of (doc, score) tuples.

        The blocking Qdrant call is offloaded via ``asyncio.to_thread`` so the
        ``asyncio.gather`` in ``retrieve_with_fusion`` genuinely parallelizes
        the main query and sub-queries instead of running them sequentially on
        the event loop.
        """
        try:
            if qdrant_filter:
                return await asyncio.to_thread(
                    self._vector_store.similarity_search_with_score,
                    query=query, k=k, filter=qdrant_filter,
                )
            return await asyncio.to_thread(
                self._vector_store.similarity_search_with_score,
                query=query, k=k,
            )
        except Exception as e:
            logger.warning("Sub-query dense search failed for '%s': %s", query[:60], e)
            return []
