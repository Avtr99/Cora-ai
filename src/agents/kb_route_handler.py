"""
Knowledge Base Route Handler

Handles KB-only query processing with relevance checking and web supplementation.
"""

import hashlib
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .protocols import (
    AnswerGeneratorProtocol,
    FusionRetrieverProtocol,
    RelevanceCheckerProtocol,
    RetrieverProtocol,
)
from .reasoning_formatter import AgentStep
from .route_processor_utils import (
    check_answer_relevance,
    clean_source_display_name,
    extract_source_titles,
    kb_top_relevance,
    remaining_budget_ms,
    source_name_from_metadata,
    try_serve_cached_answer,
)
from ..query_processing.fallback_answers import is_non_answer

if TYPE_CHECKING:
    from ..citations import CitationManager
    from .orchestrator_config import OrchestratorConfig

logger = logging.getLogger(__name__)


def _truncate_to_word_boundary(text: str, max_len: int = 80) -> str:
    """Truncate text to max_len while preserving word boundaries.

    Args:
        text: Text to truncate
        max_len: Maximum length before truncation

    Returns:
        Truncated text with "..." appended if truncated
    """
    if len(text) <= max_len:
        return text
    slice_text = text[:max_len]
    last_space = slice_text.rfind(" ")
    if last_space > 0:
        return slice_text[:last_space] + "..."
    return slice_text + "..."


def _is_explicit_non_answer(answer: str) -> bool:
    """Return whether answer text is an explicit KB non-answer fallback.

    Thin wrapper around :func:`src.query_processing.fallback_answers.is_non_answer`
    kept for backwards compatibility with internal call sites.
    """
    return is_non_answer(answer)


class KBRouteHandler:
    """Handles knowledge base route processing."""
    
    def __init__(
        self,
        retriever: RetrieverProtocol,
        answer_generator: AnswerGeneratorProtocol,
        citation_manager: "CitationManager",
        config: "OrchestratorConfig",
        validator: Optional[RelevanceCheckerProtocol] = None,
    ):
        """
        Initialize KB route handler.
        
        Args:
            retriever: Retriever implementing retrieve() method
            answer_generator: Answer generator implementing search_and_process()
            citation_manager: CitationManager instance
            config: OrchestratorConfig instance
            validator: Optional relevance checker implementing check_relevance()
            
        Raises:
            TypeError: If dependencies don't implement required protocols
            ValueError: If config is missing required attributes
        """
        # Runtime validation using isinstance against runtime_checkable protocols
        if not isinstance(retriever, RetrieverProtocol):
            raise TypeError(f"retriever must implement retrieve() method, got {type(retriever).__name__}")
        
        if not isinstance(answer_generator, AnswerGeneratorProtocol):
            raise TypeError(f"answer_generator must implement search_and_process() method, got {type(answer_generator).__name__}")
        
        required_config_attrs = [
            "retrieval_threshold", "enable_web_search", "retrieval_k",
        ]
        missing_attrs = [attr for attr in required_config_attrs if not hasattr(config, attr)]
        if missing_attrs:
            raise ValueError(f"config missing required attributes: {missing_attrs}")
        
        if validator is not None and not isinstance(validator, RelevanceCheckerProtocol):
            raise TypeError(f"validator must implement check_relevance() method if provided, got {type(validator).__name__}")
        
        self.retriever = retriever
        self.answer_generator = answer_generator
        self.citation_manager = citation_manager
        self.config = config
        self.validator = validator
    
    async def process(
        self,
        query: str,
        original_query: str,
        metadata_filters: Optional[Dict[str, Any]],
        steps: List[AgentStep],
        timeout_budget_ms: Optional[int] = None,
        web_supplement_callback: Optional[Any] = None,
        web_route_callback: Optional[Any] = None,
        finalize_citations_callback: Optional[Any] = None,
        sub_queries: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Process query using knowledge base only.
        
        Args:
            query: Rewritten query
            original_query: Original user query
            metadata_filters: Optional metadata filters
            steps: List to append AgentStep to
            timeout_budget_ms: Optional timeout budget
            web_supplement_callback: Callback for web supplementation
            web_route_callback: Callback for web route fallback
            finalize_citations_callback: Callback for citation finalization
            sub_queries: Optional sub-queries from rewriter for fusion retrieval
            
        Returns:
            Result dict with answer, sources, citations
        """
        step_start = time.time()
        
        # Retrieve from KB (use fusion retrieval when sub-queries are available)
        # allow_unfiltered_fallback=True: if the rewriter extracted filters for
        # fields that aren't payload-indexed in Qdrant, silently drop them and
        # search unfiltered rather than returning 0 results.
        try:
            if sub_queries and isinstance(self.retriever, FusionRetrieverProtocol):
                vector_results = await self.retriever.retrieve_with_fusion(
                    query=query,
                    sub_queries=sub_queries,
                    where=metadata_filters,
                    allow_unfiltered_fallback=True,
                    original_query=original_query,
                )
            else:
                vector_results = await self.retriever.retrieve(
                    query=query,
                    where=metadata_filters,
                    allow_unfiltered_fallback=True,
                    original_query=original_query,
                )
        except Exception as e:
            logger.error("Error during knowledge base retrieval: %s", e, exc_info=True)
            vector_results = {"documents": [], "metadatas": [], "ids": [], "distances": []}

        if vector_results.get("relaxed_fields"):
            logger.info(
                "Filter relaxed during KB retrieval: dropped %s",
                vector_results["relaxed_fields"],
            )

        retrieval_duration = (time.time() - step_start) * 1000
        doc_count = len(vector_results.get("documents", []))

        if doc_count == 0:
            query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()[:12]
            logger.warning(
                "KB retrieval returned 0 results (query_hash=%s) filters=%s",
                query_hash,
                metadata_filters,
            )

        # Extract highlights for frontend
        doc_highlights = self._extract_doc_highlights(vector_results, max_highlights=6)
        
        steps.append(AgentStep(
            name="Knowledge Base Retrieval",
            status="completed",
            duration_ms=round(retrieval_duration, 2),
            details={
                "documents_retrieved": doc_count,
                "threshold": self.config.retrieval_threshold,
                "highlights": doc_highlights,
            }
        ))
        
        # Fall back to web when the KB has no results OR nothing confidently
        # relevant. The second case prevents "confidently wrong" answers built
        # from topically-adjacent-but-off-topic chunks: a doc can clear the hard
        # rerank floor yet still be too weak to trust as the sole answer source.
        top_relevance = kb_top_relevance(vector_results)
        kb_min_top = float(getattr(self.config, "kb_min_top_relevance_score", 0.0) or 0.0)
        kb_not_confident = doc_count > 0 and kb_min_top > 0 and top_relevance < kb_min_top

        if (doc_count == 0 or kb_not_confident) and self.config.enable_web_search and web_route_callback:
            # Check cache before falling back to web search.
            # This handles the case where KB retrieval returns 0 results but
            # a previous successful answer is cached (e.g. starter prompts or
            # answers from a prior request with different retrieval context).
            cached_result = await try_serve_cached_answer(
                self.answer_generator,
                original_query,
                steps,
                logger=logger,
            )
            if cached_result is not None:
                return cached_result

            if doc_count == 0:
                reason = "No KB results, using web search"
            else:
                reason = (
                    f"KB relevance too low (top={top_relevance:.2f} < "
                    f"{kb_min_top:.2f}), using web search"
                )
            logger.info("Falling back to web search: %s", reason)
            steps.append(AgentStep(
                name="Fallback Decision",
                status="completed",
                details={"reason": reason}
            ))
            remaining = remaining_budget_ms(timeout_budget_ms, step_start)
            return await web_route_callback(
                query,
                steps,
                original_query=original_query,
                timeout_budget_ms=remaining,
            )
        
        # Generate answer
        gen_start = time.time()
        try:
            result = await self.answer_generator.search_and_process(original_query, vector_results)
        except Exception as e:
            duration = (time.time() - gen_start) * 1000
            logger.error("Answer generation failed: %s", e, exc_info=True)
            # Generate opaque error ID for frontend, log full details server-side only
            error_id = str(uuid.uuid4())[:8]
            steps.append(AgentStep(
                name="Answer Generation",
                status="failed",
                duration_ms=round(duration, 2),
                details={"error": "internal_error", "error_id": error_id, "source": "knowledge_base"}
            ))
            return {
                "answer": "I encountered an error generating the answer. Please try again.",
                "sources": ["error_fallback"],
                "citations": [],
                "confidence": 0.0
            }

        # If the KB had no results and web search is disabled, flag the response
        # so the frontend can show a meaningful empty-state instead of a blank answer.
        if doc_count == 0 and not self.config.enable_web_search:
            result["kb_empty"] = True
        
        gen_duration = (time.time() - gen_start) * 1000
        
        # Extract answer summary for display with safe truncation
        answer_text = result.get("answer", "")
        answer_summary = _truncate_to_word_boundary(answer_text, max_len=150) if answer_text else ""
        
        steps.append(AgentStep(
            name="Answer Generation",
            status="completed",
            duration_ms=round(gen_duration, 2),
            details={
                "source": "knowledge_base",
                "summary": answer_summary,
            }
        ))
        
        # Extract citations
        kb_citations = self.citation_manager.extract_citations_from_vector_results(
            vector_results,
            max_citations=5
        )
        result["citations"] = kb_citations
        
        # Check if supplementation needed
        should_supplement, supplement_reason = await self._check_supplementation_needed(
            result, original_query, vector_results,
        )
        
        if should_supplement and self.config.enable_web_search and web_supplement_callback:
            logger.info("Supplementing with web search: %s", supplement_reason)
            remaining = remaining_budget_ms(timeout_budget_ms, step_start)
            return await web_supplement_callback(
                original_query,
                result,
                vector_results,
                steps,
                supplement_reason=supplement_reason,
                timeout_budget_ms=remaining,
            )
        
        # Finalize citations
        coverage_score = result.get("coverage_score")
        if coverage_score is None:
            # Calculate coverage score if not provided by answer generator
            # Heuristic: based on number of documents retrieved vs requested
            if self.config.retrieval_k > 0:
                coverage_score = min(doc_count / self.config.retrieval_k, 1.0)
            else:
                coverage_score = 0.0
            result["coverage_score"] = coverage_score

        if finalize_citations_callback:
            finalize_citations_callback(result, original_query, coverage_score)

        return result
    
    async def _check_supplementation_needed(
        self,
        result: Dict[str, Any],
        original_query: str,
        vector_results: Optional[Dict[str, Any]] = None,
    ) -> tuple[bool, str]:
        """Check if KB answer needs web supplementation.

        Two triggers:
        1. The answer is an explicit non-answer fallback ("Information not
           found...").
        2. The LLM relevance check says the answer is off-topic with high
           confidence.

        The LLM relevance check (trigger 2) runs unconditionally — we do NOT
        skip it based on high rerank scores or high coverage. A doc can be
        semantically similar to the query (high rerank) yet not actually
        answer the specific question, causing the LLM to hallucinate. The
        only safe skip is the zero-cost explicit non-answer check (trigger 1).
        """
        answer = result.get("answer", "")

        if _is_explicit_non_answer(answer):
            logger.info("Triggering web supplementation due to explicit KB non-answer fallback")
            return True, "KB generation returned explicit non-answer fallback"

        if self.validator and self.config.enable_web_search:
            source_titles = extract_source_titles(vector_results) if vector_results else None
            is_irrelevant, reason = await check_answer_relevance(
                self.validator, self.config, original_query, answer, log_tag="KB",
                source_titles=source_titles,
            )
            if is_irrelevant:
                return True, reason

        return False, ""
    
    def _extract_doc_highlights(
        self,
        vector_results: Dict[str, Any],
        max_highlights: int = 2,
    ) -> List[str]:
        """Extract short snippet highlights from top documents."""
        highlights = []
        documents = vector_results.get("documents", [])
        metadatas = vector_results.get("metadatas", [])
        
        for idx, doc in enumerate(documents[:max_highlights]):
            if not doc:
                continue
            metadata = metadatas[idx] if idx < len(metadatas) else {}
            source_name = source_name_from_metadata(metadata, fallback=f"Document {idx + 1}")
            source_name = clean_source_display_name(source_name)
            snippet = _truncate_to_word_boundary(doc, max_len=80)
            highlights.append(f"{source_name}: \"{snippet}\"")
        
        remaining = len(documents) - max_highlights
        if remaining > 0:
            highlights.append(f"... and {remaining} more document(s)")
        
        return highlights
