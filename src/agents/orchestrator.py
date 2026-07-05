"""
RAG Orchestrator

Coordinates all agents in the multi-agent RAG pipeline:
1. Query Rewriter - Fix typos, expand acronyms
2. Router - Decide KB vs Web search
3. Retriever - Get documents from vector store
4. Web Search - Get web results if needed
5. Answer Generator - Synthesize final answer
6. Validator - Optional grounding check

Optimized for speed and cost while maintaining accuracy.
"""

import logging
import time
import asyncio
from typing import Dict, Any, List, Optional

from .protocols import AnswerGeneratorProtocol, RelevanceCheckerProtocol
from .query_rewriter import QueryRewriterAgent
from .router import RouterAgent, RouteDecision
from .web_search import WebSearchAgent
from .tavily_search import TavilySearchProvider
from .validator import AnswerValidator
from .route_processors import RouteProcessor
from .reasoning_formatter import AgentStep, format_reasoning_steps
from .orchestrator_config import OrchestratorConfig
from .orchestrator_query_utils import (
    query_changed_substantially,
    infer_document_id_from_query,
)
from .orchestrator_utils import (
    remaining_time_ms,
    build_timing_breakdown,
    extract_timeout_reason,
    check_timeout,
)
from .rewrite_handler import RewriteHandler
from .routing_handler import RoutingHandler
from .conversational_handler import ConversationalHandler
from ..config import get_settings, get_collection_threshold
from ..citations import CitationManager
from ..query_processing.filter_extractor import extract_filters
from ..query_processing.fallback_answers import is_cacheable_answer
from ..query_processing.llm_provider import LLMClient
from ..query_processing.citation_verifier import renumber_citation_markers

logger = logging.getLogger(__name__)


class RAGOrchestrator:
    """
    Orchestrates the multi-agent RAG pipeline.
    
    Coordinates query rewriting, routing, retrieval, web search,
    answer generation, and validation for optimal results.
    
    Thread Safety: Per-request state (steps) is isolated. Caching responsibility
    has moved to RewriteHandler and RoutingHandler. Caches are now owned and
    managed there and are NOT thread-safe. Cache misses result in recomputation
    without data corruption.
    
    Cache keys include both query text and chat history for context-aware
    caching.
    """

    @classmethod
    async def create(
        cls,
        llm_client: LLMClient,
        retriever: Any,
        answer_generator: AnswerGeneratorProtocol,
        config: Optional[OrchestratorConfig] = None,
        model_name: Optional[str] = None,
        validator: Optional[RelevanceCheckerProtocol] = None,
    ):
        """Async factory: builds the orchestrator and fetches the SQLite cache.

        ``__init__`` is synchronous, so any async singleton initialization
        (like ``get_sqlite_cache()``) happens here. This keeps the constructor
        simple and avoids awaiting inside ``__init__``.
        """
        from ..config import get_settings
        settings = get_settings()
        sqlite_cache = None
        if getattr(settings, "CACHE_ENABLED", True):
            from ..db.sqlite_cache import get_sqlite_cache
            sqlite_cache = await get_sqlite_cache()
        return cls(
            llm_client,
            retriever,
            answer_generator,
            config=config,
            model_name=model_name,
            validator=validator,
            sqlite_cache=sqlite_cache,
        )

    def __init__(
        self,
        llm_client: LLMClient,
        retriever: Any,  # ponytail: keep as Any; full retriever protocol lives in agents.protocols
        answer_generator: AnswerGeneratorProtocol,
        config: Optional[OrchestratorConfig] = None,
        model_name: Optional[str] = None,
        validator: Optional[RelevanceCheckerProtocol] = None,
        sqlite_cache: Optional[Any] = None,
    ):
        """
        Initialize the orchestrator with all required components.

        Args:
            llm_client: LLMClient instance for agent LLM calls (routing, rewriting, etc.)
            retriever: LangChainRetriever instance
            answer_generator: LLMClient instance for answer synthesis
            config: Orchestrator configuration
            model_name: Model name override for agent LLM calls (None = use client defaults)
            validator: Optional validator instance implementing check_relevance().
                If None, a default AnswerValidator is created using the configured
                GEMINI_MODEL_RELEVANCE model.
        """
        self.config = config or OrchestratorConfig()
        self.retriever = retriever
        self.answer_generator = answer_generator

        # Track fire-and-forget background tasks (cache writes) to prevent
        # garbage collection before completion. See asyncio.create_task docs.
        self._background_tasks: set = set()

        # Initialize agents — all receive the LLMClient, not a raw genai.Client
        query_rewriter = QueryRewriterAgent(llm_client, model_name)
        router = RouterAgent(llm_client, model_name=None)  # Use default Lite model for speed

        # Initialize pluggable search provider based on config
        settings = get_settings()
        search_provider_name = getattr(settings, "SEARCH_PROVIDER", "tavily").lower()
        search_provider = None
        if search_provider_name == "tavily":
            search_provider = TavilySearchProvider()
        else:
            logger.warning(f"Unknown search provider: {search_provider_name}. Falling back to Tavily.")
            search_provider = TavilySearchProvider()

        self.web_search = WebSearchAgent(llm_client, model_name, search_provider=search_provider)
        # ponytail: validator is injectable; default uses the client's configured
        # relevance model (model_relevance), which resolves to the provider's lite
        # or main model by default.
        self.validator = validator or AnswerValidator(llm_client, model_name)
        self.citation_manager = CitationManager(
            min_relevance_score=get_collection_threshold(
                settings, "CITATION_MIN_RELEVANCE_SCORE"
            )
        )

        # Initialize handlers with in-memory + SQLite caching
        self.rewrite_handler = RewriteHandler(
            query_rewriter=query_rewriter,
            use_quick_rewrite=self.config.use_quick_rewrite,
            cache_ttl=settings.REWRITE_CACHE_TTL,
            sqlite_cache=sqlite_cache,
            sqlite_ttl_seconds=getattr(settings, "CACHE_TTL_SECONDS", 86400),
        )
        self.routing_handler = RoutingHandler(
            router=router,
            default_route=self.config.default_route,
            cache_ttl=settings.ROUTE_CACHE_TTL,
            sqlite_cache=sqlite_cache,
            sqlite_ttl_seconds=getattr(settings, "CACHE_TTL_SECONDS", 86400),
        )

        # Initialize route processor
        self.route_processor = RouteProcessor(
            retriever=retriever,
            answer_generator=answer_generator,
            web_search=self.web_search,
            citation_manager=self.citation_manager,
            config=self.config,
            validator=self.validator,
        )
        
        # Initialize conversational handler for fast greeting/chat responses
        # model_name=None lets the LLMClient use its lite model
        self.conversational_handler = ConversationalHandler(llm_client, model_name=None)

    def _remaining_time_ms(self, start_time: float) -> Optional[int]:
        """Get remaining orchestrator budget in milliseconds."""
        return remaining_time_ms(self.config.max_total_time_ms, start_time)

    async def _try_early_cache_hit(
        self,
        query: str,
        steps: List[AgentStep],
        start_time: float,
    ) -> Optional[Dict[str, Any]]:
        """Check the query cache before any rewriting/routing/retrieval.

        Returns a fully-formed result dict (with ``metadata`` and
        ``reasoning_steps`` populated, route set to ``"cache"``) on a hit, or
        ``None`` on a miss.  Shared by the non-streaming and streaming
        orchestrator entry points.
        """
        check_cache = getattr(self.answer_generator, "check_query_cache", None)
        if check_cache is None:
            return None
        try:
            cached_result = await check_cache(query)
        except Exception as cache_exc:
            logger.debug("Early query cache check failed: %s", cache_exc)
            return None

        if cached_result is None or not isinstance(cached_result, dict):
            return None

        cached_answer = str(cached_result.get("answer", "") or "")
        if not cached_answer:
            return None

        logger.debug("Serving from early query cache check")
        total_time = (time.time() - start_time) * 1000
        cached_result.setdefault("sources", [])
        # citations must be Optional[CitationResponse] (a dict or None) to satisfy
        # the Response model. A raw list here caused a Pydantic ValidationError on
        # the streaming endpoint: the early cache-hit path yields cached_result
        # directly, bypassing the orchestrator's citation-formatting block.
        cached_result.setdefault("citations", None)
        cached_result["metadata"] = {
            "original_query": query,
            "rewritten_query": query,
            "route": "cache",
            "route_confidence": 1.0,
            "total_time_ms": round(total_time, 2),
            "rewrite_info": {},
            "timeout_exceeded": False,
            "timeout_reason": None,
            "timing_breakdown": {},
            "truncated": False,
        }
        if "reasoning_steps" not in cached_result:
            cached_result["reasoning_steps"] = format_reasoning_steps(steps)
        return cached_result

    async def _persist_result_to_cache(
        self,
        query: str,
        result: Dict[str, Any],
    ) -> None:
        """Persist the final result to the SQLite cache.

        Called by the orchestrator after the complete reasoning chain, metadata,
        and citations have been assembled. This ensures cached entries are
        identical to what a live request returns, so cache hits are consistent
        with cache misses.

        All route answers (KB, web, hybrid) are persisted with a 24h TTL.
        The query-only cache key means the same question will serve the same
        answer for the configured TTL, surviving application restarts.

        This method is called as a fire-and-forget task via _spawn_cache_persist()
        to avoid blocking the response. The result dict is already fully built
        before this method is called, so cache write failures are non-critical.

        Args:
            query: Original user query (un-rewritten).
            result: Final result dict with ``reasoning_steps`` already set.
        """
        persist_to_cache = getattr(self.answer_generator, "persist_to_cache", None)
        if persist_to_cache is None:
            return
        if not is_cacheable_answer(result.get("answer", ""), result.get("sources")):
            return
        try:
            await persist_to_cache(query, result)
        except Exception as e:
            logger.debug("Failed to persist result to SQLite cache: %s", e)

    def _spawn_cache_persist(self, query: str, result: Dict[str, Any]) -> None:
        """Schedule cache persistence as a fire-and-forget background task.

        The task is stored in ``self._background_tasks`` to prevent garbage
        collection before completion (per asyncio.create_task docs). The task
        removes itself from the set on completion to avoid unbounded growth.

        A shallow snapshot of ``result`` is captured now.  Nested dicts
        (``metadata``, ``citations``) are shared references, but they are
        set earlier in ``process()`` and never mutated after this point,
        so the snapshot is safe for serialization.
        """
        result_snapshot = dict(result)
        task = asyncio.create_task(self._persist_result_to_cache(query, result_snapshot))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _try_conversational(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]],
        steps: List[AgentStep],
        start_time: float,
        use_llm_classification: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Attempt conversational handling and return a finalized result dict.

        Returns a fully-formed conversational result (with ``metadata`` and
        ``reasoning_steps`` populated, route set to ``"conversational"``) on
        success, or ``None`` to signal the caller to proceed with the RAG
        pipeline (either the handler declined, or ``handle`` returned
        ``ROUTE_TO_RAG``).

        Args:
            use_llm_classification: When False, only the cheap regex heuristic
                (``is_conversational``) is consulted — no LLM call. Intended for
                the pre-cache gate so greetings short-circuit without a wasted
                cache lookup. When True, the LLM intent classification
                (``classify_intent``) is consulted — intended for the
                post-cache-miss gate to catch short ambiguous queries the regex
                missed.
        """
        if use_llm_classification:
            should = await self.conversational_handler.classify_intent(query, chat_history)
        else:
            should = self.conversational_handler.is_conversational(query, chat_history)
        if not should:
            return None

        conv_result = await self.conversational_handler.handle(query, chat_history, steps)
        if conv_result is None:
            # Handler signalled ROUTE_TO_RAG — fall through to the RAG pipeline.
            return None

        total_time = (time.time() - start_time) * 1000
        conv_result["metadata"] = {
            "original_query": query,
            "rewritten_query": query,
            "route": "conversational",
            "route_confidence": 1.0,
            "total_time_ms": round(total_time, 2),
            "rewrite_info": {},
            "timeout_exceeded": False,
            "timeout_reason": None,
            "timing_breakdown": build_timing_breakdown(steps),
            "truncated": False,
        }
        conv_result["reasoning_steps"] = format_reasoning_steps(steps)
        return conv_result

    async def process(
        self, 
        query: str,
        metadata_filters: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Process a user query through the multi-agent pipeline.
        
        Args:
            query: User's original query
            metadata_filters: Optional metadata filters for retrieval (e.g., {"Developer": "Nike"})
            chat_history: Optional list of conversation messages for context resolution
              Each message should have 'role' ('user', 'assistant', 'system') and 'content' keys
            
        Returns:
            Dict with answer, sources, reasoning steps, and metadata
        """
        start_time = time.time()
        steps: List[AgentStep] = []  # Per-request state (thread-safe)
        
        # Set timeout deadline
        deadline = None
        if self.config.max_total_time_ms > 0:
            deadline = start_time + (self.config.max_total_time_ms / 1000)
        
        try:
            # OPTIMIZATION: Conversational Gate — cheap heuristic first.
            # Bypass the entire RAG pipeline for clear greetings/conversational
            # queries using only the regex heuristic (no LLM call). Greetings are
            # never cached (conversational responses don't go through
            # persist_to_cache), so checking the cache for them is wasted work —
            # especially the SQLite call.
            conv_result = await self._try_conversational(
                query, chat_history, steps, start_time, use_llm_classification=False
            )
            if conv_result is not None:
                logger.debug("Conversational query detected, bypassing RAG pipeline")
                return conv_result

            # OPTIMIZATION: Early Query Cache Check
            # Check in-memory and SQLite caches before any rewriting, routing,
            # or retrieval. This serves previously answered queries instantly.
            # Runs after the cheap conversational heuristic so greetings skip
            # the cache, and before the LLM intent classification so cache hits
            # avoid any LLM cost.
            cached_result = await self._try_early_cache_hit(query, steps, start_time)
            if cached_result is not None:
                return cached_result

            # OPTIMIZATION: Conversational Gate — LLM intent classification.
            # Only paid on a cache miss, for short ambiguous queries the regex
            # heuristic missed. Cached per normalized query (in-memory LRU), so
            # the cost is paid at most once per query per warm instance.
            conv_result = await self._try_conversational(
                query, chat_history, steps, start_time, use_llm_classification=True
            )
            if conv_result is not None:
                logger.debug("Conversational query detected after cache miss, bypassing RAG pipeline")
                return conv_result

            # OPTIMIZATION: Run rewrite and route in parallel
            # Router works on original query while rewriter runs
            # Re-route only if query changes substantially
            
            if self.config.enable_rewriting and self.config.enable_routing:
                # Parallel execution for latency optimization
                # Use route_raw to avoid recording step during preliminary routing
                (rewritten_query, rewrite_info), (prelim_route, prelim_confidence, prelim_reason) = await asyncio.gather(
                    self.rewrite_handler.rewrite(query, chat_history, steps, self.config.enable_rewriting),
                    self.routing_handler.route_raw(query, self.config.enable_routing)
                )
                
                # Check if query changed substantially
                if query_changed_substantially(query, rewritten_query):
                    # Significant change - re-route with rewritten query
                    logger.debug("Query changed substantially, re-routing")
                    route, route_confidence, route_reason = await self.routing_handler.route_raw(
                        rewritten_query, self.config.enable_routing
                    )
                    route_source = "re-routed after rewrite"
                else:
                    # Minor change - use preliminary route
                    logger.debug("Query change minimal, using preliminary route")
                    route = prelim_route
                    route_confidence = prelim_confidence
                    route_reason = prelim_reason
                    route_source = "preliminary (query unchanged)"
                
                # Record ONE routing step with final decision
                steps.append(AgentStep(
                    name="Query Routing",
                    status="completed",
                    duration_ms=0.0,  # Already completed during parallel phase
                    details={
                        "route": route.value,
                        "confidence": route_confidence,
                        "reason": route_reason,
                        "source": route_source,
                    },
                ))
            
            elif self.config.enable_rewriting:
                # Only rewriting enabled
                rewritten_query, rewrite_info = await self.rewrite_handler.rewrite(
                    query, chat_history, steps, self.config.enable_rewriting
                )
                route, route_confidence, route_reason = await self.routing_handler.route(
                    rewritten_query, steps, self.config.enable_routing
                )
            
            elif self.config.enable_routing:
                # Only routing enabled
                rewritten_query = query
                rewrite_info = {}
                route, route_confidence, route_reason = await self.routing_handler.route(
                    query, steps, self.config.enable_routing
                )
            
            else:
                # Both disabled
                rewritten_query = query
                rewrite_info = {}
                route = self.config.default_route
                route_confidence = 1.0
                route_reason = "Default route (rewriting and routing disabled)"

            # Extract structured filters from rewritten query to enable metadata filtering
            rewritten_filters = {}
            cleaned_rewritten_query = rewritten_query
            try:
                cleaned_rewritten_query, rewritten_filters = extract_filters(rewritten_query)
            except Exception as exc:
                logger.warning("Failed to extract filters from rewritten query: %s", exc)

            if rewritten_filters:
                merged_filters = dict(metadata_filters or {})
                for key, value in rewritten_filters.items():
                    merged_filters.setdefault(key, value)
                metadata_filters = merged_filters
                rewritten_query = cleaned_rewritten_query
                if isinstance(rewrite_info, dict):
                    rewrite_info = {**rewrite_info, "filters": rewritten_filters}

            inferred_document_id = (
                infer_document_id_from_query(rewritten_query)
                or infer_document_id_from_query(query)
            )
            if inferred_document_id:
                merged_filters = dict(metadata_filters or {})
                merged_filters.setdefault("document_id", inferred_document_id)
                metadata_filters = merged_filters
                if isinstance(rewrite_info, dict):
                    existing_filters = dict(rewrite_info.get("filters") or {})
                    existing_filters.setdefault("document_id", inferred_document_id)
                    rewrite_info = {**rewrite_info, "filters": existing_filters}
            
            # Check timeout after rewriting and routing
            timeout_resp = check_timeout(deadline, start_time, steps, "rewriting/routing", query)
            if timeout_resp:
                return timeout_resp
            
            # Extract sub-queries from rewrite info for fusion retrieval
            sub_queries: Optional[List[str]] = None
            if isinstance(rewrite_info, dict):
                raw_sub_queries = rewrite_info.get("sub_queries", [])
                if isinstance(raw_sub_queries, list) and raw_sub_queries:
                    if getattr(get_settings(), "ENABLE_SUBQUERY_FUSION", True):
                        sub_queries = [sq for sq in raw_sub_queries if isinstance(sq, str) and sq.strip()]
                        if sub_queries:
                            logger.debug("Fusion retrieval enabled with %d sub-queries", len(sub_queries))

            # Step 3: Execute based on route (delegated to RouteProcessor)
            remaining_budget_ms = self._remaining_time_ms(start_time)
            if route == RouteDecision.KNOWLEDGE_BASE:
                result = await self.route_processor.process_kb_route(
                    rewritten_query,
                    query,
                    metadata_filters,
                    steps,
                    timeout_budget_ms=remaining_budget_ms,
                    sub_queries=sub_queries,
                )
            elif route == RouteDecision.WEB_SEARCH:
                result = await self.route_processor.process_web_route(
                    rewritten_query,
                    steps,
                    original_query=query,
                    timeout_budget_ms=remaining_budget_ms,
                )
            else:  # HYBRID
                result = await self.route_processor.process_hybrid_route(
                    rewritten_query,
                    query,
                    metadata_filters,
                    steps,
                    timeout_budget_ms=remaining_budget_ms,
                )
            
            # Check timeout after main processing
            timeout_resp = check_timeout(deadline, start_time, steps, "main processing", query)
            if timeout_resp:
                return timeout_resp
            
            # Step 4: Optional Validation
            if self.config.enable_validation:
                result = await self._validate_answer(result, steps)
            else:
                # Always emit a validation step so the frontend shows it
                steps.append(AgentStep(
                    name="Answer Validation",
                    status="skipped",
                    details={"reason": "Validation disabled for speed"}
                ))
            
            # Add metadata
            total_time = (time.time() - start_time) * 1000
            
            # Check if timeout exceeded
            timeout_exceeded = (self.config.max_total_time_ms > 0 and 
                              total_time > self.config.max_total_time_ms)
            
            # Extract and format citations
            citations = result.get("citations", [])
            answer_text = result.get("answer", "")

            if result.get("_citations_finalized"):
                # Route processor already filtered, suppressed, aligned, and
                # renumbered.  Skip the redundant work and go straight to
                # response formatting.
                filtered_citations = citations
            else:
                # No finalization callback ran — do it here.
                filtered_citations = self.citation_manager.filter_citations_by_answer(
                    citations, answer_text, query=query
                )

                coverage_score = result.get("coverage_score", 1.0)
                if self.citation_manager.should_suppress_citations(
                    query, answer_text, filtered_citations, coverage_score
                ):
                    filtered_citations = []

                # Renumber inline citation markers so their numbers match the
                # filtered citation list. Markers referencing filtered-out
                # sources are removed. Also runs when filtered is empty
                # (suppressed) to strip orphaned markers.
                if answer_text and (filtered_citations or citations):
                    renumbered = renumber_citation_markers(answer_text, citations, filtered_citations)
                    if renumbered != answer_text:
                        result["answer"] = renumbered

            citation_info = self.citation_manager.format_citations_for_response(
                filtered_citations,
                include_snippets=True
            )
            
            result["metadata"] = {
                "original_query": query,
                "rewritten_query": rewritten_query,
                "route": route.value,
                "route_confidence": route_confidence,
                "total_time_ms": round(total_time, 2),
                "rewrite_info": rewrite_info,
                "timeout_exceeded": timeout_exceeded,
                "timeout_reason": extract_timeout_reason(steps),
                "timing_breakdown": build_timing_breakdown(steps),
                "truncated": result.get("truncated", False),
                "kb_empty": result.get("kb_empty", False),
            }
            result["citations"] = citation_info
            result["reasoning_steps"] = format_reasoning_steps(steps)

            # Persist to SQLite cache after the complete reasoning chain is
            # assembled so cache hits are identical to live responses.
            # Fire-and-forget to avoid blocking the response.
            self._spawn_cache_persist(query, result)

            logger.info(
                "Query timing breakdown",
                extra={
                    "route": route.value,
                    "total_time_ms": round(total_time, 2),
                    "timeout_reason": result["metadata"].get("timeout_reason"),
                    "timing_breakdown": result["metadata"].get("timing_breakdown", {}),
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Orchestrator error: {e}", exc_info=True)  # Full trace for debugging
            return {
                "answer": "I encountered an error processing your query. Please try again.",
                "sources": [],
                "error": "Internal processing error",  # Generic message for users
                "reasoning_steps": format_reasoning_steps(steps),
            }

    async def _validate_answer(self, result: Dict[str, Any], steps: List[AgentStep]) -> Dict[str, Any]:
        """Optionally validate the answer grounding."""
        if not self.config.enable_validation:
            return result
        
        answer = result.get("answer", "")
        
        # Skip validation for short answers
        if self.config.validate_long_answers_only and len(answer) < 200:
            steps.append(AgentStep(
                name="Answer Validation",
                status="skipped",
                details={"reason": "Answer too short"}
            ))
            return result
        
        step_start = time.time()
        
        # Get source texts for validation (actual document content, not just names)
        source_texts = result.get("source_documents", result.get("documents", []))
        
        # Fallback to source names if no document content available
        if not source_texts:
            source_texts = result.get("sources", [])
            logger.warning(
                "Validation using source names instead of document content. "
                "Validation quality may be reduced."
            )
        
        validation = await self.validator.validate(answer, source_texts)
        duration = (time.time() - step_start) * 1000
        
        steps.append(AgentStep(
            name="Answer Validation",
            status="completed",
            duration_ms=round(duration, 2),
            details={
                "is_grounded": validation.get("is_grounded", True),
                "confidence": validation.get("confidence", 0.5)
            }
        ))
        
        result["validation"] = validation
        return result
