"""
LangChain-Based Retriever for Agentic RAG

Simplified retriever using LangChain components:
- Pluggable embeddings (Voyage / Cohere / Ollama) via provider factory
- QdrantVectorStore for similarity search
- Pluggable reranker (Voyage / Cohere / none) via reranker factory

This retriever provides the retrieval interface consumed by the RAG
orchestrator, with filter handling, result post-processing, and fusion
retrieval delegated to dedicated modules.

Usage:
    from src.retrieval.langchain_retriever import LangChainRetriever
    
    retriever = LangChainRetriever()
    results = await retriever.retrieve("What are the requirements for VM0007?")
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple

from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

from ..config import get_settings, get_collection_threshold
from ..embeddings import create_embeddings
from .reranker_factory import create_reranker
from .retrieval_utils import MultiRoundRetrievalMixin, ResultFilter
from .filter_builder import QdrantFilterBuilder, handle_filter_search_error
from .result_processor import (
    apply_post_processing,
    empty_result,
    format_results,
    rerank_results,
)
from .structured_context import build_structured_context
from .structured_queries import StructuredListSpec
from .fusion_retrieval import FusionRetriever

logger = logging.getLogger(__name__)

# Enumeration lists are small entity inventories (13 CCP-eligible programs);
# 500 is far above anything the corpus holds. Aggregates need every matching
# row or the headline count is a lower bound, and the largest methodology in
# the corpus (ACM0002) has ~1,500 project rows — measured at ~390ms to scroll
# payload-only, against a rerank call of comparable cost that it replaces.
_MAX_ENUMERATE_SCROLL = 500
_MAX_AGGREGATE_SCROLL = 5000
_SCROLL_BATCH = 1000


class LangChainRetriever(MultiRoundRetrievalMixin):
    """
    LangChain-based retriever with pluggable reranking.

    Provides the retrieval interface consumed by the agentic RAG orchestrator.
    
    Architecture:
    - Dense vector search via LangChain QdrantVectorStore
    - Pluggable reranker for quality (Voyage / Cohere / none)
    - Methodology code boosting for VCM-specific queries
    - Multi-round retrieval for better coverage
    - Multi-query fusion for complex queries
    """
    
    DEFAULT_COLLECTION = "cora_dense_only"
    INITIAL_CANDIDATES = 30
    
    def __init__(
        self,
        collection_name: Optional[str] = None,
        enable_reranking: bool = True,
        retrieval_rounds: int = 1
    ):
        """
        Initialize the LangChain retriever.
        
        Args:
            collection_name: Qdrant collection name (default: cora_dense_only)
            enable_reranking: Whether to use reranking (default: True)
            retrieval_rounds: Number of retrieval rounds (default: 1)
        """
        self.collection_name = collection_name or self.DEFAULT_COLLECTION
        self.enable_reranking = enable_reranking
        
        # Initialize multi-round retrieval mixin
        MultiRoundRetrievalMixin.__init__(self, retrieval_rounds)
        
        self._vector_store: Optional[QdrantVectorStore] = None
        self._reranker = None
        self._initialized = False
        self._filter_builder: Optional[QdrantFilterBuilder] = None
        self._fusion_retriever: Optional[FusionRetriever] = None
    
    def _ensure_initialized(self):
        """Lazy initialization of clients."""
        if self._initialized:
            return
        
        settings = get_settings()
        
        if not settings.QDRANT_URL:
            raise ValueError("QDRANT_URL is required")

        qdrant_client = QdrantClient(
            url=settings.QDRANT_URL,
            timeout=60,
        )
        
        # Pluggable embeddings (Voyage / Cohere / Ollama)
        embeddings = create_embeddings()

        self._vector_store = QdrantVectorStore(
            client=qdrant_client,
            collection_name=self.collection_name,
            embedding=embeddings,
            validate_collection_config=False,
        )

        # Pluggable reranker (Voyage / Cohere / none)
        if self.enable_reranking:
            self._reranker = create_reranker()
            if self._reranker is None:
                # RERANK_PROVIDER=none — disable reranking
                self.enable_reranking = False

        # Initialize helper modules
        self._filter_builder = QdrantFilterBuilder(
            vector_store=self._vector_store,
            collection_name=self.collection_name,
        )
        self._fusion_retriever = FusionRetriever(
            vector_store=self._vector_store,
            reranker=self._reranker,
            enable_reranking=self.enable_reranking,
            initial_candidates=self.INITIAL_CANDIDATES,
            filter_builder=self._filter_builder,
        )
        
        self._initialized = True
        logger.info(
            "LangChainRetriever initialized (collection=%s, reranking=%s, rounds=%s)",
            self.collection_name, self.enable_reranking, self.retrieval_rounds
        )
    
    async def retrieve(
        self,
        query: str,
        where: Optional[Dict[str, Any]] = None,
        allow_unfiltered_fallback: bool = False,
        original_query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve documents matching the query with multi-round retrieval.
        
        Args:
            query: User query string (possibly rewritten by the rewriter).
            where: Optional metadata filter dict (e.g., {"doc_type": "methodology"})
            allow_unfiltered_fallback: If True, allows fallback to unfiltered search
                when a recognized Qdrant filter error occurs. Defaults to False
                (fail-closed).
            original_query: The un-rewritten user query, used for the lexical
                overlap guard. When provided, the guard matches content words
                against the original phrasing (e.g. acronyms like "VCS") rather
                than the expanded rewrite (e.g. "Verified Carbon Standard"),
                which would unfairly penalize on-topic docs. Defaults to
                ``query`` when None (no rewrite or caller doesn't have it).
        
        Returns:
            Dict with keys: ids, documents, metadatas, distances, scores
        """
        self._ensure_initialized()
        
        if not query or not query.strip():
            return empty_result()
        
        round1_config = self._round_configs[0]
        candidates_count = self.INITIAL_CANDIDATES if self.enable_reranking else round1_config.k
        
        # Build filter
        qdrant_filter, supported_filters = await self._build_filter_with_validation(
            where, allow_unfiltered_fallback
        )
        relaxed_fields: List[str] = []
        
        # Round 1: vector search
        docs_with_scores = await self._perform_vector_search(
            query, candidates_count, qdrant_filter, allow_unfiltered_fallback
        )
        
        if not docs_with_scores:
            # Try filter relaxation if no results
            if qdrant_filter and supported_filters:
                relaxed = await self._filter_builder.relax_and_retry(
                    query, supported_filters, candidates_count,
                )
                if relaxed:
                    docs_with_scores, relaxed_fields = relaxed
            
            if not docs_with_scores:
                logger.info("No results found for query: %s", query[:50])
                return empty_result()
        
        logger.debug("Round 1 dense search returned %d candidates", len(docs_with_scores))

        # Multi-round: expand the raw candidate pool if round 1 was sparse.
        # This runs BEFORE reranking so the reranker gets a larger pool to
        # select from. Round 2 fetches more candidates and deduplicates by
        # page_content against round 1 results.
        if self.should_expand_candidates(len(docs_with_scores), round1_config.k):
            docs_with_scores = await self._expand_candidates(
                query, docs_with_scores, qdrant_filter, candidates_count
            )

        # Rerank the (possibly expanded) candidate pool, or fall back to
        # dense scores with threshold filtering when reranking is disabled.
        settings = get_settings()
        if self.enable_reranking and self._reranker and len(docs_with_scores) > 1:
            results = await asyncio.to_thread(
                rerank_results,
                self._reranker,
                query, docs_with_scores, round1_config.k,
            )
            # Drop off-topic docs below the rerank relevance floor. If nothing
            # clears it, results become empty -> orchestrator falls back to web.
            results = ResultFilter.apply_relevance_floor(
                results,
                float(get_collection_threshold(settings, "RERANK_SCORE_THRESHOLD") or 0.0)
            )
        else:
            formatted = format_results(docs_with_scores[:round1_config.k])
            results = ResultFilter.filter_by_threshold_dict(
                formatted, round1_config.threshold
            )

        # Pre-LLM lexical overlap guard: if the retrieved docs collectively
        # share too few content words with the query, they are off-topic even
        # if the reranker scored them above the floor. Returns empty so the
        # orchestrator falls back to web. Zero-cost (string matching only).
        # Passes BOTH the rewritten query and the original: per-doc overlap
        # is the MAX across both forms, so acronym expansion (e.g. "VCS" →
        # "Verified Carbon Standard") does not unfairly lower overlap for docs
        # that mention either form.
        overlap_threshold = float(
            get_collection_threshold(settings, "QUERY_DOC_OVERLAP_THRESHOLD") or 0.0
        )
        if overlap_threshold > 0:
            results = ResultFilter.apply_overlap_guard(
                results, query, overlap_threshold,
                alternate_query=original_query,
            )

        # Apply post-processing (diversification + methodology boosting)
        max_per_source = int(max(getattr(settings, 'MAX_CHUNKS_PER_SOURCE', 5), 0))
        results = apply_post_processing(results, query, max_per_source)
        
        if relaxed_fields:
            results["relaxed_fields"] = relaxed_fields
        
        return results
    
    async def retrieve_with_fusion(
        self,
        query: str,
        sub_queries: List[str],
        where: Optional[Dict[str, Any]] = None,
        allow_unfiltered_fallback: bool = False,
        original_query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve documents using multi-query fusion for complex queries.

        Delegates to FusionRetriever. Falls back to standard retrieve() if
        no sub-queries are provided.

        Args:
            original_query: The un-rewritten user query, used for the lexical
                overlap guard (see ``retrieve`` for rationale).
        """
        self._ensure_initialized()
        return await self._fusion_retriever.retrieve_with_fusion(
            query=query,
            sub_queries=sub_queries,
            where=where,
            allow_unfiltered_fallback=allow_unfiltered_fallback,
            fallback_retrieve=self.retrieve,
            original_query=original_query,
        )
    
    async def retrieve_structured(
        self,
        spec: StructuredListSpec,
    ) -> Dict[str, Any]:
        """Retrieve matching records by Qdrant metadata scroll rather than vector search.

        Unlike :meth:`retrieve` (top-K semantically similar chunks), this
        uses ``QdrantClient.scroll`` with a payload filter to visit **every**
        record matching the filter. Scrolling everything is what makes the
        counts in the facts header true; how much of it reaches the prompt is
        decided by ``spec.mode`` in :func:`build_structured_context`, which
        emits the full list only for ``enumerate``.

        ``enumerate`` and ``aggregate`` results carry
        ``structured_mode``, which tells downstream code the context is
        pre-formatted and self-sufficient: skip per-chunk context limits,
        skip web supplementation, skip quiz generation. ``supplement``
        results carry no such marker, so the caller prepends the facts block
        to normal retrieval and web fallback stays available.

        Args:
            spec: A :class:`StructuredListSpec` produced by
                :func:`detect_structured_list_query`.

        Returns:
            Dict with keys ``ids``, ``documents``, ``metadatas``,
            ``distances``, ``scores``, and — for non-supplement modes —
            ``structured_mode``.
        """
        self._ensure_initialized()

        qdrant_filter = (
            self._filter_builder.build_filter(spec.qdrant_filter)
            if spec.qdrant_filter
            else None
        )

        client = self._vector_store.client
        collection = self.collection_name
        scroll_cap = (
            _MAX_ENUMERATE_SCROLL if spec.mode == "enumerate" else _MAX_AGGREGATE_SCROLL
        )

        all_records: list = []
        offset = None
        next_offset = None

        while len(all_records) < scroll_cap:
            records, next_offset = await asyncio.to_thread(
                client.scroll,
                collection_name=collection,
                scroll_filter=qdrant_filter,
                limit=min(_SCROLL_BATCH, scroll_cap - len(all_records)),
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            for record in records:
                if not record.payload:
                    continue
                payload = record.payload
                metadata = payload.get("metadata") or {}
                all_records.append({
                    "id": str(record.id),
                    "json_index": metadata.get("json_index", 0),
                    "metadata": metadata,
                    "document": payload.get("page_content", ""),
                })

            if next_offset is None:
                break
            offset = next_offset

        if not all_records:
            logger.info(
                "Structured scroll returned 0 records for filter=%s; caller should fall back",
                spec.qdrant_filter,
            )
            return empty_result()

        # A non-None next_offset at the cap means more records matched than
        # were scrolled, so counts become lower bounds and the context says so.
        hit_scroll_cap = len(all_records) >= scroll_cap and next_offset is not None
        # Rows can also be partial because the source file was cut at the
        # ingestion row limit; the indexer flags those rows in the payload.
        source_truncated = any(
            bool((record.get("metadata") or {}).get("dataset_truncated"))
            for record in all_records
        )
        # 10% headroom under the prompt limit covers header overhead, so the
        # prompt-layer truncation stays a backstop that never fires here.
        # Only enumerate mode can approach it; the other modes emit a fixed
        # facts block plus a bounded sample.
        max_chars = (
            int(get_settings().MAX_COMPLETE_LIST_CHARS * 0.9)
            if spec.mode == "enumerate"
            else None
        )
        context_text, record_count = build_structured_context(
            all_records, spec, hit_scroll_cap=hit_scroll_cap, max_chars=max_chars,
        )
        if record_count == 0:
            # Metadata could not identify a single record. Fall back to vector
            # retrieval rather than present an empty dataset as an answer.
            logger.info(
                "Structured scroll produced no identifiable records for filter=%s",
                spec.qdrant_filter,
            )
            return empty_result()

        logger.info(
            "Structured scroll mode=%s filter=%s scrolled=%d records=%d capped=%s chars=%d",
            spec.mode, spec.qdrant_filter, len(all_records),
            record_count, hit_scroll_cap, len(context_text),
        )

        # This document is synthesised from many rows, so it gets its own
        # identity. Inheriting an arbitrary row's metadata would caption the
        # citation for a 1,474-row census with one random project's name.
        first_source = (
            (all_records[0].get("metadata") or {}).get("source", "")
            if all_records
            else ""
        )
        metadata = {
            "source": first_source or spec.source,
            "title": spec.display_name,
            "doc_type": "dataset",
            "structured_mode": spec.mode,
            "structured_record_count": record_count,
        }
        result = {
            "ids": [f"structured:{spec.record_type}:{spec.mode}"],
            "documents": [context_text],
            "metadatas": [metadata],
            "distances": [0.0],
            "scores": [1.0],
        }
        if spec.mode != "supplement":
            result["structured_mode"] = spec.mode
        if source_truncated:
            # The indexed rows are a prefix of the source file, so the result
            # must not claim complete coverage or suppress web supplementation.
            metadata["structured_partial"] = True
            result["structured_partial"] = True
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    
    async def _build_filter_with_validation(
        self,
        where: Optional[Dict[str, Any]],
        allow_unfiltered_fallback: bool,
    ) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
        """Build a validated Qdrant filter.

        Returns ``(qdrant_filter, supported_filters)``. Both are ``None`` when
        ``where`` is empty. Relaxed-field tracking is handled at the call site
        via ``relax_and_retry``, not here.
        """
        if not where:
            return None, None

        qdrant_filter, supported_filters = await self._filter_builder.build_validated_filter(
            where, allow_unfiltered_fallback
        )
        return qdrant_filter, supported_filters
    
    async def _perform_vector_search(
        self,
        query: str,
        k: int,
        qdrant_filter,
        allow_unfiltered_fallback: bool,
    ) -> List:
        """Perform vector search with comprehensive error handling.

        Handles Qdrant index-missing errors with optional unfiltered fallback.
        Returns an empty list on fail-closed errors.
        """
        effective_fallback = bool(
            allow_unfiltered_fallback or getattr(self, "allow_unfiltered_fallback", False)
        )

        if not qdrant_filter:
            return await asyncio.to_thread(
                self._vector_store.similarity_search_with_score, query=query, k=k
            )

        try:
            return await asyncio.to_thread(
                self._vector_store.similarity_search_with_score,
                query=query, k=k, filter=qdrant_filter,
            )
        except UnexpectedResponse as filter_err:
            should_fallback, error_message, status_code = handle_filter_search_error(
                filter_err, effective_fallback
            )

            if should_fallback:
                logger.warning(
                    "Filtered search failed with Qdrant index error; "
                    "retrying unfiltered search. status_code=%s error=%s",
                    status_code, error_message,
                )
                return await asyncio.to_thread(
                    self._vector_store.similarity_search_with_score, query=query, k=k
                )

            logger.error(
                "Filtered search failed and was blocked (fail-closed). "
                "allow_unfiltered_fallback=%s status_code=%s error=%s",
                effective_fallback, status_code, error_message,
            )
            return []
        except Exception as filter_err:
            logger.exception(
                "Filtered search failed with unexpected exception type=%s; failing closed.",
                type(filter_err).__name__,
            )
            return []
    
    async def _expand_candidates(
        self,
        query: str,
        existing_docs: List,
        qdrant_filter,
        candidates_count: int,
    ) -> List:
        """Round 2: fetch more candidates and merge by page_content dedup.

        Expands the raw candidate pool before reranking. Round 2 fetches
        ``ROUND2_CANDIDATES`` additional candidates from the same dense index
        to find documents round 1 missed. Duplicates (by page_content) are
        removed so the reranker doesn't see the same document twice.
        """
        round2_config = self._round_configs[1]
        round2_k = round2_config.k

        try:
            if qdrant_filter:
                docs_round2 = await asyncio.to_thread(
                    self._vector_store.similarity_search_with_score,
                    query=query, k=round2_k, filter=qdrant_filter,
                )
            else:
                docs_round2 = await asyncio.to_thread(
                    self._vector_store.similarity_search_with_score,
                    query=query, k=round2_k,
                )

            # Deduplicate by page_content against round 1
            seen_content = {doc.page_content for doc, _ in existing_docs}
            merged = list(existing_docs)
            for doc, score in docs_round2:
                if doc.page_content not in seen_content:
                    seen_content.add(doc.page_content)
                    merged.append((doc, score))

            logger.info(
                "Round 2 expanded candidates: %d → %d (fetched %d, %d new)",
                len(existing_docs), len(merged), len(docs_round2),
                len(merged) - len(existing_docs),
            )
            return merged
        except Exception as e:
            logger.warning("Round 2 expansion failed, using round 1 candidates: %s", e)
            return existing_docs


# ------------------------------------------------------------------
# Module-level retriever cache (parameter-keyed singleton)
# ------------------------------------------------------------------

_retriever_cache: Dict[Tuple[str, bool, int], LangChainRetriever] = {}
_retriever_cache_lock = asyncio.Lock()


async def get_langchain_retriever(
    collection_name: Optional[str] = None,
    enable_reranking: bool = True,
    retrieval_rounds: int = 1,
) -> LangChainRetriever:
    """
    Get or create a LangChain retriever for the given parameters.
    
    Instances are cached by (collection_name, enable_reranking, retrieval_rounds)
    so that different parameter combinations each get their own retriever while
    repeated calls with the same parameters reuse the existing one.
    
    Args:
        collection_name: Qdrant collection name
        enable_reranking: Whether to enable Voyage reranking
        retrieval_rounds: Number of retrieval rounds
    
    Returns:
        LangChainRetriever instance
    """
    resolved_name = collection_name or LangChainRetriever.DEFAULT_COLLECTION
    cache_key = (resolved_name, enable_reranking, retrieval_rounds)
    
    async with _retriever_cache_lock:
        if cache_key not in _retriever_cache:
            _retriever_cache[cache_key] = LangChainRetriever(
                collection_name=resolved_name,
                enable_reranking=enable_reranking,
                retrieval_rounds=retrieval_rounds,
            )
        return _retriever_cache[cache_key]
