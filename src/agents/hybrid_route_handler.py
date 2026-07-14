"""
Hybrid Route Handler

Handles hybrid (KB + Web) query processing.
"""

import asyncio
import inspect
import logging
import time
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from .protocols import (
    AnswerGeneratorProtocol,
    ConfigProtocol,
    RelevanceCheckerProtocol,
    RetrieverProtocol,
    WebSearchProtocol,
)
from .reasoning_formatter import AgentStep
from .route_processor_utils import (
    check_answer_relevance,
    clean_source_display_name,
    compute_merged_coverage_score,
    derive_web_timeout_ms,
    extract_source_chunks,
    extract_source_titles,
    kb_top_relevance,
    normalize_sources,
    remaining_budget_ms,
    source_name_from_metadata,
)
if TYPE_CHECKING:
    from ..citations import CitationManager

logger = logging.getLogger(__name__)


class HybridRouteHandler:
    """Handles hybrid route processing (KB + Web)."""

    def __init__(
        self,
        retriever: RetrieverProtocol,
        answer_generator: AnswerGeneratorProtocol,
        web_search: WebSearchProtocol,
        citation_manager: "CitationManager",
        config: ConfigProtocol,
        validator: Optional[RelevanceCheckerProtocol] = None,
    ):
        """
        Initialize hybrid route handler.

        Args:
            retriever: LangChainRetriever instance
            answer_generator: GeminiClient instance
            web_search: WebSearchAgent instance
            citation_manager: CitationManager instance
            config: OrchestratorConfig instance
            validator: Optional RelevanceChecker instance
        """
        self.retriever = retriever
        self.answer_generator = answer_generator
        self.web_search = web_search
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
        finalize_citations_callback: Optional[Callable[..., Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process query using both KB and web search.
        
        Args:
            query: Rewritten query
            original_query: Original user query
            metadata_filters: Optional metadata filters
            steps: List to append AgentStep to
            timeout_budget_ms: Optional timeout budget
            finalize_citations_callback: Callback for citation finalization
            
        Returns:
            Result dict with answer, sources, citations
        """
        step_start = time.time()
        remaining_budget = remaining_budget_ms(timeout_budget_ms, step_start)
        web_timeout_ms = derive_web_timeout_ms(remaining_budget)
        
        # Execute KB and web in parallel or sequentially
        if self.config.parallel_retrieval:
            vector_results, web_results = await self._parallel_retrieval(
                query, metadata_filters, web_timeout_ms, original_query
            )
        else:
            vector_results, web_results = await self._sequential_retrieval(
                query, metadata_filters, web_timeout_ms, original_query
            )
        
        retrieval_duration = (time.time() - step_start) * 1000
        
        steps.append(AgentStep(
            name="Hybrid Retrieval",
            status="completed",
            duration_ms=round(retrieval_duration, 2),
            details={
                "kb_documents": len(vector_results.get("documents", [])),
                "web_sources": len(web_results.get("sources", [])),
                "parallel": self.config.parallel_retrieval,
                "web_timed_out": bool(web_results.get("timed_out")),
                "web_timeout_ms": web_results.get("timeout_ms", web_timeout_ms),
            }
        ))
        
        # Drop low-confidence KB context so the hybrid route does not synthesize
        # an answer from topically-adjacent-but-off-topic chunks. A doc can clear
        # the rerank floor and still be wrong for the query (e.g., VM0047 ARR for
        # "Just Transition Mechanism"). If KB is weak, answer from web only.
        top_kb_relevance = kb_top_relevance(vector_results)
        kb_min_top = float(getattr(self.config, "kb_min_top_relevance_score", 0.0) or 0.0)
        kb_low_confidence = (
            kb_min_top > 0
            and vector_results.get("documents")
            and top_kb_relevance < kb_min_top
        )
        if kb_low_confidence:
            logger.info(
                "Hybrid route discarding KB context (top_kb_relevance=%.3f < %.3f)",
                top_kb_relevance,
                kb_min_top,
            )
            vector_results = {
                "documents": [],
                "metadatas": [],
                "ids": [],
                "distances": [],
                "scores": [],
            }

        # Synthesize answer
        kb_context = "\n\n".join(vector_results.get("documents", []))
        kb_sources = self._extract_sources(vector_results)
        
        gen_start = time.time()
        
        if kb_context and web_results.get("answer") and not web_results.get("timed_out"):
            # Combine KB context with web results
            remaining_budget = remaining_budget_ms(timeout_budget_ms, step_start)
            hybrid_web_timeout_ms = derive_web_timeout_ms(remaining_budget)
            result = await self.web_search.search_with_kb_context(
                query=original_query,
                kb_context=kb_context,
                kb_sources=kb_sources,
                timeout_ms=hybrid_web_timeout_ms,
            )
            if result.get("sources"):
                result["sources"] = normalize_sources(result["sources"])
        elif kb_context:
            # KB only
            result = await self.answer_generator.search_and_process(original_query, vector_results)
        else:
            # Web only
            result = {
                "answer": web_results.get("answer", "No answer available."),
                "sources": [(s.get("title") or s.get("url") or "web") for s in web_results.get("sources", [])],
                "quiz": web_results.get("quiz"),
                "suggested_prompts": web_results.get("suggested_prompts"),
                "truncated": web_results.get("truncated", False),
            }
        
        gen_duration = (time.time() - gen_start) * 1000
        
        steps.append(AgentStep(
            name="Answer Synthesis",
            status="completed",
            duration_ms=round(gen_duration, 2),
            details={"method": "hybrid"}
        ))

        # Post-generation relevance check: if the synthesized answer is not
        # actually about the user's question, fall back to the web-only answer.
        # This is the last line of defense against off-topic KB context leaking
        # into the final response. The check runs regardless of whether web
        # timed out — if web is unavailable and the hybrid answer is off-topic,
        # we return a graceful "couldn't verify" response rather than shipping
        # an unverified off-topic answer.
        if self.validator and self.config.enable_web_search:
            is_irrelevant, _ = await check_answer_relevance(
                self.validator, self.config,
                original_query, result.get("answer", ""), log_tag="Hybrid",
                source_titles=extract_source_titles(vector_results),
                source_chunks=extract_source_chunks(vector_results),
            )
            if is_irrelevant:
                web_usable = bool(web_results.get("answer")) and not web_results.get("timed_out")
                if web_usable:
                    logger.info("Hybrid answer off-topic, using web-only fallback")
                    result = {
                        "answer": web_results.get("answer", "No answer available."),
                        "sources": [
                            (s.get("title") or s.get("url") or "web")
                            for s in web_results.get("sources", [])
                        ],
                        "quiz": web_results.get("quiz"),
                        "suggested_prompts": web_results.get("suggested_prompts"),
                        "truncated": web_results.get("truncated", False),
                    }
                else:
                    logger.info(
                        "Hybrid answer off-topic and web unavailable (timed_out=%s); "
                        "returning unverified-state response",
                        web_results.get("timed_out"),
                    )
                    result = {
                        "answer": (
                            "I could not find a verified answer to your question. "
                            "The knowledge base did not contain directly relevant "
                            "information and web verification was unavailable. "
                            "Please try rephrasing your question."
                        ),
                        "sources": [],
                        "coverage_score": 0.0,
                    }
                steps.append(AgentStep(
                    name="Hybrid Relevance Check",
                    status="completed",
                    duration_ms=0.0,
                    details={
                        "reason": (
                            "Hybrid answer off-topic, used web-only fallback"
                            if web_usable
                            else "Hybrid answer off-topic, web unavailable — returned unverified-state response"
                        ),
                    },
                ))

        # Merge citations and keep only sources that are actually grounded in the final answer.
        kb_citations = self.citation_manager.extract_citations_from_vector_results(
            vector_results,
            max_citations=5
        )
        web_citations = self.citation_manager.extract_citations_from_web_results(
            web_results,
            max_citations=3
        )
        merged_citations = self.citation_manager.merge_citations(
            kb_citations,
            web_citations,
            max_total=5
        )
        # Defer filtering, suppression, and renumbering to the
        # finalize_citations_callback (RouteProcessor._finalize_citations),
        # which handles source-type alignment and marker renumbering in one
        # pass.  Setting citations to the merged set gives the callback the
        # full original list so renumber mapping is correct.
        result["citations"] = merged_citations
        
        # Use coverage_score from result if available, otherwise compute from merged citations
        coverage_score = result.get("coverage_score")
        if coverage_score is None:
            # Compute based on citation coverage using canonical helper
            total_citations = len(merged_citations)
            kb_citation_count = len(kb_citations)
            web_citation_count = len(web_citations)
            coverage_score = compute_merged_coverage_score(
                total_citations, kb_citation_count, web_citation_count
            )
        result["coverage_score"] = coverage_score
        
        if finalize_citations_callback:
            # Handle both sync and async callbacks, with optional coverage_score support
            sig = inspect.signature(finalize_citations_callback)
            accepts_coverage_score = 'coverage_score' in sig.parameters
            
            if accepts_coverage_score:
                callback_result = finalize_citations_callback(result, original_query, coverage_score=coverage_score)
            else:
                callback_result = finalize_citations_callback(result, original_query)
            if inspect.isawaitable(callback_result):
                await callback_result
        
        return result
    
    async def _parallel_retrieval(
        self,
        query: str,
        metadata_filters: Optional[Dict[str, Any]],
        web_timeout_ms: Optional[int],
        original_query: Optional[str] = None,
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Execute KB and web retrieval in parallel."""
        kb_task = self.retriever.retrieve(
            query=query,
            where=metadata_filters,
            allow_unfiltered_fallback=True,
            original_query=original_query,
        )
        web_task = self.web_search.search(query, timeout_ms=web_timeout_ms)
        
        results = await asyncio.gather(kb_task, web_task, return_exceptions=True)
        
        # Handle exceptions gracefully
        if isinstance(results[0], Exception):
            logger.error("KB retrieval failed in parallel mode: %s", results[0], exc_info=results[0])
            vector_results = {"documents": [], "metadatas": [], "ids": [], "distances": []}
        else:
            vector_results = results[0]
            if vector_results.get("relaxed_fields"):
                logger.info(
                    "Filter relaxed during hybrid parallel KB retrieval: dropped %s",
                    vector_results["relaxed_fields"],
                )

        if isinstance(results[1], Exception):
            logger.error("Web search failed in parallel mode: %s", results[1], exc_info=results[1])
            web_results = {"answer": "", "sources": [], "grounded": False}
        else:
            web_results = results[1]
        
        return vector_results, web_results
    
    async def _sequential_retrieval(
        self,
        query: str,
        metadata_filters: Optional[Dict[str, Any]],
        web_timeout_ms: Optional[int],
        original_query: Optional[str] = None,
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Execute KB and web retrieval sequentially with error handling."""
        # KB retrieval with exception handling
        try:
            vector_results = await self.retriever.retrieve(
                query=query,
                where=metadata_filters,
                allow_unfiltered_fallback=True,
                original_query=original_query,
            )
            if vector_results.get("relaxed_fields"):
                logger.info(
                    "Filter relaxed during hybrid sequential KB retrieval: dropped %s",
                    vector_results["relaxed_fields"],
                )
        except Exception as e:
            logger.error("KB retrieval failed in sequential mode: %s", e, exc_info=True)
            vector_results = {"documents": [], "metadatas": [], "ids": [], "distances": []}

        # Web search with exception handling
        try:
            web_results = await self.web_search.search(query, timeout_ms=web_timeout_ms)
        except Exception as e:
            logger.error("Web search failed in sequential mode: %s", e, exc_info=True)
            web_results = {"answer": "", "sources": [], "grounded": False}
        
        return vector_results, web_results
    
    def _extract_sources(self, vector_results: Dict[str, Any]) -> List[str]:
        """Extract source names from vector results."""
        sources = []
        metadatas = vector_results.get("metadatas", [])

        for metadata in metadatas:
            if metadata and isinstance(metadata, dict):
                source = source_name_from_metadata(metadata)
                if source:
                    source = clean_source_display_name(source)
                if source and source not in sources:
                    sources.append(source)

        return sources
