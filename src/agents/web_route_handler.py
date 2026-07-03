"""
Web Route Handler

Handles web search route processing and web supplementation.
"""

import logging
import time
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .protocols import (
    AnswerGeneratorProtocol,
    ConfigProtocol,
    RetrieverProtocol,
    WebSearchProtocol,
)
from .reasoning_formatter import AgentStep
from .route_processor_utils import (
    derive_web_timeout_ms,
    normalize_sources,
)
from ..utils.security import sanitize_error_message

if TYPE_CHECKING:
    from ..citations import CitationManager

logger = logging.getLogger(__name__)


class WebRouteHandler:
    """Handles web search route processing."""
    
    def __init__(
        self,
        web_search: WebSearchProtocol,
        retriever: RetrieverProtocol,
        answer_generator: AnswerGeneratorProtocol,
        citation_manager: "CitationManager",
        config: ConfigProtocol,
    ):
        """
        Initialize web route handler.
        
        Args:
            web_search: Web search implementing search() and search_with_kb_context()
            retriever: Retriever implementing retrieve() (for fallback)
            answer_generator: Answer generator implementing search_and_process() (for fallback)
            citation_manager: CitationManager instance
            config: Config implementing enable_web_search, retrieval_threshold, retrieval_k
        """
        self.web_search = web_search
        self.retriever = retriever
        self.answer_generator = answer_generator
        self.citation_manager = citation_manager
        self.config = config
    
    async def process(
        self,
        query: str,
        steps: List[AgentStep],
        original_query: Optional[str] = None,
        timeout_budget_ms: Optional[int] = None,
        finalize_citations_callback: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Process query using web search only.
        
        Args:
            query: Query string
            steps: List to append AgentStep to
            original_query: Original user query
            timeout_budget_ms: Optional timeout budget
            finalize_citations_callback: Callback for citation finalization
            
        Returns:
            Result dict with answer, sources, citations
        """
        step_start = time.time()
        web_timeout_ms = derive_web_timeout_ms(timeout_budget_ms)
        
        try:
            # Use the (rewritten) query for search — it has resolved pronouns/context.
            # original_query is only used for citation filtering downstream.
            result = await self.web_search.search(query, timeout_ms=web_timeout_ms)
            duration = (time.time() - step_start) * 1000
            timed_out = bool(result.get("timed_out"))

            steps.append(AgentStep(
                name="Web Search",
                status="fallback" if timed_out else "completed",
                duration_ms=round(duration, 2),
                details={
                    "sources_found": len(result.get("sources", [])),
                    "grounded": result.get("grounded", False),
                    "timed_out": timed_out,
                    "timeout_ms": result.get("timeout_ms", web_timeout_ms),
                }
            ))

            sources = [(s.get("title") or s.get("url") or "web") for s in result.get("sources", [])]
            # Mark web search failures/timeouts as error fallback so the frontend
            # treats the answer as a failed response (no recommendations, retry UI).
            search_failed = bool(result.get("error")) or (timed_out and not sources)
            if search_failed:
                sources = ["error_fallback"]

            web_citations = self.citation_manager.extract_citations_from_web_results(
                result,
                max_citations=3
            )

            coverage_score = self._compute_web_coverage_score(
                citation_count=len(web_citations),
                source_count=len(result.get("sources", [])),
                timed_out=timed_out,
            )
            
            response = {
                "answer": result.get("answer", ""),
                "sources": sources if sources else ["web_search"],
                "web_sources": result.get("sources", []),
                "citations": web_citations,
                "quiz": result.get("quiz"),
                "suggested_prompts": result.get("suggested_prompts"),
                "coverage_score": coverage_score,
                "truncated": result.get("truncated", False),
            }

            if finalize_citations_callback:
                finalize_citations_callback(response, original_query or query, coverage_score=coverage_score)
            
            return response
            
        except Exception as e:
            duration = (time.time() - step_start) * 1000
            logger.error("Error during web search: %s", e, exc_info=True)
            
            error_details = sanitize_error_message(str(e))
            steps.append(AgentStep(
                name="Web Search",
                status="failed",
                duration_ms=round(duration, 2),
                details={"error": error_details}
            ))
            
            return {
                "answer": "I couldn't retrieve information from web search. Please try rephrasing your question, or check that the Tavily API key is configured correctly.",
                "sources": ["error_fallback"],
                "web_sources": [],
                "citations": [],
                "quiz": None,
                "suggested_prompts": None,
                "coverage_score": 0.0,
                "truncated": False,
            }
    
    def _compute_merged_coverage_score(
        self,
        total_citations: int,
    ) -> float:
        """
        Compute coverage score for merged KB and web citations.

        Args:
            total_citations: Total number of citations (merged)

        Returns:
            Coverage score between 0.0 and 1.0
        """
        if total_citations >= 5:
            return 1.0
        elif total_citations >= 3:
            return 0.8
        elif total_citations >= 1:
            return 0.6
        else:
            return 0.0

    def _compute_web_coverage_score(
        self,
        citation_count: int,
        source_count: int,
        timed_out: bool,
    ) -> float:
        """
        Compute coverage score for web search based on results quality.

        Args:
            citation_count: Number of web citations extracted
            source_count: Number of web sources returned
            timed_out: Whether search timed out

        Returns:
            Coverage score between 0.0 and 1.0
        """
        # Penalize for timeout
        if timed_out:
            return 0.3
        
        # Base score from citations and sources
        if citation_count >= 3 and source_count >= 3:
            return 1.0
        elif citation_count >= 2 and source_count >= 2:
            return 0.8
        elif citation_count >= 1 and source_count >= 1:
            return 0.6
        elif citation_count >= 1 or source_count >= 1:
            return 0.4
        else:
            return 0.2
    
    def _build_limited_context(
        self,
        documents: List[str],
        max_chars: int = 10000,
        truncation_marker: str = "[...additional documents truncated...]"
    ) -> str:
        """
        Build context string from documents with size limit.
        
        Args:
            documents: List of document strings
            max_chars: Maximum character limit for context
            truncation_marker: Marker to append when truncated
            
        Returns:
            Joined context string within size limit
        """
        if not documents:
            return ""
        
        context_parts = []
        current_length = 0
        
        for doc in documents:
            # Account for separator ("\n\n" = 2 chars) except for first doc
            separator_len = 2 if context_parts else 0
            doc_len = len(doc)
            
            # Check if adding this doc would exceed limit (including truncation marker)
            projected_len = current_length + separator_len + doc_len + len(truncation_marker)
            if projected_len > max_chars:
                # If context_parts is empty, this is the first (and only) doc - truncate it to fit
                if not context_parts:
                    available_space = max_chars - separator_len - len(truncation_marker)
                    if available_space > 0:
                        truncated_doc = doc[:available_space]
                        context_parts.append(truncated_doc + truncation_marker)
                    break
                # Only add truncation marker if we have content and it fits within limit
                if current_length + separator_len + len(truncation_marker) <= max_chars:
                    context_parts.append(truncation_marker)
                break
            
            context_parts.append(doc)
            current_length += separator_len + doc_len
        
        return "\n\n".join(context_parts)
    
    async def supplement(
        self,
        query: str,
        kb_result: Dict[str, Any],
        vector_results: Dict[str, Any],
        steps: List[AgentStep],
        supplement_reason: str = "Low KB coverage",
        timeout_budget_ms: Optional[int] = None,
        finalize_citations_callback: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Supplement KB answer with web search.
        
        Args:
            query: Query string
            kb_result: KB result to supplement
            vector_results: Vector retrieval results
            steps: List to append AgentStep to
            supplement_reason: Reason for supplementation
            timeout_budget_ms: Optional timeout budget
            finalize_citations_callback: Callback for citation finalization
            
        Returns:
            Supplemented result dict
        """
        step_start = time.time()
        
        # Build kb_context with size limit to respect token/memory limits
        documents = vector_results.get("documents", [])
        kb_context = self._build_limited_context(documents, max_chars=10000)
        kb_sources = kb_result.get("sources", [])
        
        web_failed = False
        error_msg = None
        web_timed_out = False
        web_timeout_ms = derive_web_timeout_ms(timeout_budget_ms)

        try:
            result = await self.web_search.search_with_kb_context(
                query=query,
                kb_context=kb_context,
                kb_sources=kb_sources,
                timeout_ms=web_timeout_ms,
            )
            web_timed_out = bool(result.get("timed_out"))
            if web_timed_out:
                web_failed = True
                error_msg = "Web supplementation timed out"
                result = kb_result.copy()
        except Exception as e:
            logger.error("Web supplementation failed: %s", e, exc_info=True)
            result = kb_result.copy()
            web_failed = True
            error_msg = sanitize_error_message(str(e), context="web supplementation")

        # Normalize sources
        if result.get("sources"):
            result["sources"] = normalize_sources(result["sources"])

        duration = (time.time() - step_start) * 1000

        if web_failed:
            step_status = "fallback"
            step_details = {
                "reason": "Web supplementation failed, used KB fallback",
                "error": error_msg,
                "timed_out": web_timed_out,
                "timeout_ms": web_timeout_ms,
            }
        else:
            step_status = "completed"
            step_details = {
                "reason": supplement_reason,
                "timed_out": False,
                "timeout_ms": web_timeout_ms,
            }
            
        steps.append(AgentStep(
            name="Web Supplementation",
            status=step_status,
            duration_ms=round(duration, 2),
            details=step_details
        ))
        
        # Merge citations. Extract web citations from the raw web source dicts
        # (result["web_sources"]) before result["sources"] is normalized to plain
        # strings, otherwise the URLs and source types are lost and the citations
        # get filtered out by the finalizer.
        kb_citations = self.citation_manager.extract_citations_from_vector_results(
            vector_results,
            max_citations=5
        )
        web_citations = self.citation_manager.extract_citations_from_web_results(
            {"sources": result.get("web_sources", [])},
            max_citations=3
        )
        merged_citations = self.citation_manager.merge_citations(
            kb_citations,
            web_citations,
            max_total=5
        )
        result["citations"] = merged_citations
        
        # Use coverage_score from result if available, otherwise compute from merged citations
        coverage_score = result.get("coverage_score")
        if coverage_score is None:
            # Compute based on citation coverage using canonical helper
            coverage_score = self._compute_merged_coverage_score(
                len(merged_citations)
            )
        
        if finalize_citations_callback:
            finalize_citations_callback(result, query, coverage_score=coverage_score)
        
        return result
