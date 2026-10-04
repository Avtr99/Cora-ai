"""
Route Processors for RAG Orchestrator

Thin coordinator that delegates to specialized route handlers:
- KBRouteHandler: Knowledge Base route
- WebRouteHandler: Web Search route + supplementation
- HybridRouteHandler: Hybrid route (KB + Web)
"""
import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING

from .protocols import (
    AnswerGeneratorProtocol,
    ConfigProtocol,
    RelevanceCheckerProtocol,
    RetrieverProtocol,
    WebSearchProtocol,
)
from .route_processor_utils import get_relevance_checker
from .kb_route_handler import KBRouteHandler
from .web_route_handler import WebRouteHandler
from .hybrid_route_handler import HybridRouteHandler

if TYPE_CHECKING:
    from .reasoning_formatter import AgentStep
    from ..citations import CitationManager

logger = logging.getLogger(__name__)


class RouteProcessor:
    """
    Thin coordinator for route processing.

    Delegates to specialized handlers for KB, web, and hybrid routes.
    """

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
        Initialize the route processor.

        Args:
            retriever: LangChainRetriever instance
            answer_generator: GeminiClient instance
            web_search: WebSearchAgent instance
            citation_manager: CitationManager instance
            config: OrchestratorConfig instance
            validator: Optional AnswerValidator / RelevanceChecker instance
        """
        self.citation_manager = citation_manager
        self.config = config
        relevance_checker = validator or get_relevance_checker(answer_generator, logger)

        # Initialize specialized handlers
        self.kb_handler = KBRouteHandler(
            retriever=retriever,
            answer_generator=answer_generator,
            citation_manager=citation_manager,
            config=config,
            validator=relevance_checker,
        )
        self.web_handler = WebRouteHandler(
            web_search=web_search,
            retriever=retriever,
            answer_generator=answer_generator,
            citation_manager=citation_manager,
            config=config,
        )
        self.hybrid_handler = HybridRouteHandler(
            retriever=retriever,
            answer_generator=answer_generator,
            web_search=web_search,
            citation_manager=citation_manager,
            config=config,
            validator=relevance_checker,
        )

    def _finalize_citations(
        self,
        result: Dict[str, Any],
        query: str,
        coverage_score: float = 1.0,
    ) -> None:
        """Select the displayed citations from the answer's own markers."""
        self.citation_manager.finalize(result, query, coverage_score)
    
    async def process_kb_route(
        self,
        query: str,
        original_query: str,
        metadata_filters: Optional[Dict[str, Any]],
        steps: List["AgentStep"],
        timeout_budget_ms: Optional[int] = None,
        sub_queries: Optional[List[str]] = None,
        allow_query_only_cache: bool = True,
    ) -> Dict[str, Any]:
        """Process query using knowledge base only.

        Args:
            query: Rewritten/optimized query for retrieval
            original_query: Original user query text
            metadata_filters: Optional filters to constrain KB search
            steps: Accumulated agent steps for reasoning trace
            timeout_budget_ms: Remaining time budget for this operation
            sub_queries: Optional list of focused sub-queries derived from the
                original query to guide multi-query fusion retrieval; passed
                through to kb_handler.process for parallel dense search.
            allow_query_only_cache: When False, skip the unscoped query-only
                cache fallback. Must be False for follow-up turns, whose text
                ("what are the risks") is not unique to one conversation.

        Returns:
            Dict with answer, sources, citations, and metadata
        """
        return await self.kb_handler.process(
            query=query,
            original_query=original_query,
            metadata_filters=metadata_filters,
            steps=steps,
            timeout_budget_ms=timeout_budget_ms,
            web_supplement_callback=self.supplement_with_web,
            web_route_callback=self.process_web_route,
            finalize_citations_callback=self._finalize_citations,
            sub_queries=sub_queries,
            allow_query_only_cache=allow_query_only_cache,
        )

    async def process_web_route(
        self,
        query: str,
        steps: List["AgentStep"],
        original_query: Optional[str] = None,
        timeout_budget_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Process query using web search only."""
        return await self.web_handler.process(
            query=query,
            steps=steps,
            original_query=original_query,
            timeout_budget_ms=timeout_budget_ms,
            finalize_citations_callback=self._finalize_citations,
        )

    async def process_hybrid_route(
        self,
        query: str,
        original_query: str,
        metadata_filters: Optional[Dict[str, Any]],
        steps: List["AgentStep"],
        timeout_budget_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Process query using both KB and web search."""
        return await self.hybrid_handler.process(
            query=query,
            original_query=original_query,
            metadata_filters=metadata_filters,
            steps=steps,
            timeout_budget_ms=timeout_budget_ms,
            finalize_citations_callback=self._finalize_citations,
        )

    async def supplement_with_web(
        self,
        query: str,
        kb_result: Dict[str, Any],
        vector_results: Dict[str, Any],
        steps: List["AgentStep"],
        supplement_reason: str = "Low KB coverage",
        timeout_budget_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Supplement KB answer with web search."""
        return await self.web_handler.supplement(
            query=query,
            kb_result=kb_result,
            vector_results=vector_results,
            steps=steps,
            supplement_reason=supplement_reason,
            timeout_budget_ms=timeout_budget_ms,
            finalize_citations_callback=self._finalize_citations,
        )
