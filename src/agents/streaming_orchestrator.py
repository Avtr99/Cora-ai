"""Streaming orchestrator for the RAG pipeline.

This module extends ``RAGOrchestrator`` with a single streaming entry point. The
non-streaming orchestrator remains unchanged; the streaming path only adds the
minimal glue needed to emit token events for the KB route while reusing the
existing rewrite/routing logic and web/hybrid handlers.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, AsyncGenerator

from .orchestrator import RAGOrchestrator
from .streaming_handler import KBStreamingHandler
from .reasoning_formatter import AgentStep, format_reasoning_steps
from .orchestrator_utils import check_timeout, build_timing_breakdown, extract_timeout_reason
from .route_processor_utils import emit_text_as_token_events
from .router import RouteDecision
from ..query_processing.streaming_rag_wrapper import StreamingRAGWrapper
from ..query_processing.filter_extractor import extract_filters
from ..query_processing.citation_verifier import renumber_citation_markers
from ..config import get_settings
from .orchestrator_query_utils import (
    query_changed_substantially,
    infer_document_id_from_query,
)

logger = logging.getLogger(__name__)


class StreamingRAGOrchestrator(RAGOrchestrator):
    """RAG orchestrator with a streaming query path."""

    def __init__(self, *args, **kwargs):
        """Initialize the streaming orchestrator.

        Args are forwarded to ``RAGOrchestrator``. The streaming KB handler is
        created lazily on first use so that importing this module does not force
        heavyweight dependencies at import time.
        """
        super().__init__(*args, **kwargs)
        self._streaming_handler: Optional[KBStreamingHandler] = None

    def _get_streaming_handler(self) -> KBStreamingHandler:
        """Return the streaming KB handler, creating it lazily."""
        if self._streaming_handler is None:
            # Wrap the existing answer generator (LLMClient) so we reuse the
            # same underlying connection/config instead of creating a second client.
            streaming_answer_generator = StreamingRAGWrapper(self.answer_generator)
            self._streaming_handler = KBStreamingHandler(
                retriever=self.retriever,
                answer_generator=streaming_answer_generator,
                citation_manager=self.citation_manager,
                config=self.config,
                validator=self.validator,
            )
        return self._streaming_handler

    async def _prepare_routing(
        self,
        query: str,
        metadata_filters: Optional[Dict[str, Any]],
        chat_history: Optional[List[Dict[str, str]]],
        steps: List[AgentStep],
        start_time: float,
    ) -> Optional[Dict[str, Any]]:
        """Run rewrite and routing for the streaming path.

        Returns a completed timeout result dict directly, or a routing decision
        dict with route, rewritten_query, metadata_filters, etc. The
        conversational gate is handled by the caller (``process_stream``) before
        this method is invoked.
        """
        # Parallel rewrite + route
        if self.config.enable_rewriting and self.config.enable_routing:
            (rewritten_query, rewrite_info), (prelim_route, prelim_confidence, prelim_reason) = await asyncio.gather(
                self.rewrite_handler.rewrite(query, chat_history, steps, self.config.enable_rewriting),
                self.routing_handler.route_raw(query, self.config.enable_routing)
            )

            if query_changed_substantially(query, rewritten_query):
                logger.debug("Query changed substantially in stream, re-routing")
                route, route_confidence, route_reason = await self.routing_handler.route_raw(
                    rewritten_query, self.config.enable_routing
                )
                route_source = "re-routed after rewrite"
            else:
                route = prelim_route
                route_confidence = prelim_confidence
                route_reason = prelim_reason
                route_source = "preliminary (query unchanged)"

            steps.append(AgentStep(
                name="Query Routing",
                status="completed",
                duration_ms=0.0,
                details={
                    "route": route.value,
                    "confidence": route_confidence,
                    "reason": route_reason,
                    "source": route_source,
                },
            ))
        elif self.config.enable_rewriting:
            rewritten_query, rewrite_info = await self.rewrite_handler.rewrite(
                query, chat_history, steps, self.config.enable_rewriting
            )
            route, route_confidence, route_reason = await self.routing_handler.route(
                rewritten_query, steps, self.config.enable_routing
            )
        elif self.config.enable_routing:
            rewritten_query = query
            rewrite_info = {}
            route, route_confidence, route_reason = await self.routing_handler.route(
                query, steps, self.config.enable_routing
            )
        else:
            rewritten_query = query
            rewrite_info = {}
            route = self.config.default_route
            route_confidence = 1.0
            route_reason = "Default route (rewriting and routing disabled)"

        # Extract filters and inferred document id
        rewritten_filters = {}
        cleaned_rewritten_query = rewritten_query
        try:
            cleaned_rewritten_query, rewritten_filters = extract_filters(rewritten_query)
        except Exception as exc:
            logger.warning("Failed to extract filters from rewritten query in stream: %s", exc)

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

        timeout_resp = check_timeout(
            start_time + (self.config.max_total_time_ms / 1000) if self.config.max_total_time_ms > 0 else None,
            start_time,
            steps,
            "rewriting/routing",
            query,
        )
        if timeout_resp:
            return timeout_resp

        sub_queries: Optional[List[str]] = None
        if isinstance(rewrite_info, dict):
            raw_sub_queries = rewrite_info.get("sub_queries", [])
            if isinstance(raw_sub_queries, list) and raw_sub_queries:
                if getattr(get_settings(), "ENABLE_SUBQUERY_FUSION", True):
                    sub_queries = [sq for sq in raw_sub_queries if isinstance(sq, str) and sq.strip()]

        return {
            "route": route,
            "rewritten_query": rewritten_query,
            "rewrite_info": rewrite_info,
            "metadata_filters": metadata_filters,
            "route_confidence": route_confidence,
            "route_reason": route_reason,
            "sub_queries": sub_queries,
        }

    async def process_stream(
        self,
        query: str,
        metadata_filters: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        emit_tokens: bool = True,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream-process a query through the RAG pipeline.

        Yields:
            - ``{"type": "status", "status": "..."}`` events
            - ``{"type": "token", "chunk": "..."}`` events (skipped when emit_tokens=False)
            - ``{"type": "final", "result": {...}}`` event
        """
        start_time = time.time()
        steps: List[AgentStep] = []

        deadline = None
        if self.config.max_total_time_ms > 0:
            deadline = start_time + (self.config.max_total_time_ms / 1000)

        yield {"type": "status", "status": "accepted"}
        yield {"type": "status", "status": "processing"}

        async def _emit_answer_tokens(text: str) -> AsyncGenerator[Dict[str, Any], None]:
            """Yield token events for a pre-computed answer, unless suppressed."""
            if emit_tokens:
                async for ev in emit_text_as_token_events(text):
                    yield ev

        try:
            # OPTIMIZATION: Conversational Gate — cheap heuristic first.
            # Bypass the entire RAG pipeline for clear greetings using only the
            # regex heuristic (no LLM call). Greetings are never cached, so a
            # cache lookup for them is wasted work (esp. the SQLite call).
            conv_result = await self._try_conversational(
                query, chat_history, steps, start_time, use_llm_classification=False
            )
            if conv_result is not None:
                logger.debug("Conversational query detected in stream, bypassing RAG pipeline")
                yield {"type": "status", "status": "generating"}
                async for ev in _emit_answer_tokens(conv_result.get("answer", "")):
                    yield ev
                yield {"type": "final", "result": conv_result}
                return

            # OPTIMIZATION: Early Query Cache Check
            # Check in-memory and SQLite caches before any rewriting, routing, or retrieval.
            # Runs after the cheap heuristic (so greetings skip the cache) and
            # before the LLM intent classification (so cache hits are served
            # with zero LLM cost).
            cached_result = await self._try_early_cache_hit(query, steps, start_time)
            if cached_result is not None:
                cached_answer = str(cached_result.get("answer", "") or "")
                logger.debug("Serving from early query cache check in stream")
                yield {"type": "status", "status": "generating"}
                async for ev in _emit_answer_tokens(cached_answer):
                    yield ev
                yield {"type": "final", "result": cached_result}
                return

            # OPTIMIZATION: Conversational Gate — LLM intent classification.
            # Only paid on a cache miss, for short ambiguous queries the regex
            # missed. Cached per normalized query (in-memory LRU).
            conv_result = await self._try_conversational(
                query, chat_history, steps, start_time, use_llm_classification=True
            )
            if conv_result is not None:
                logger.debug("Conversational query detected in stream after cache miss, bypassing RAG pipeline")
                yield {"type": "status", "status": "generating"}
                async for ev in _emit_answer_tokens(conv_result.get("answer", "")):
                    yield ev
                yield {"type": "final", "result": conv_result}
                return

            routing = await self._prepare_routing(
                query=query,
                metadata_filters=metadata_filters,
                chat_history=chat_history,
                steps=steps,
                start_time=start_time,
            )

            if isinstance(routing, dict) and (
                routing.get("error") == "Request timeout"
                or routing.get("metadata", {}).get("timeout_exceeded")
            ):
                # Timeout result returned directly by ``_prepare_routing``.
                result = routing
                yield {"type": "status", "status": "generating"}
                async for ev in _emit_answer_tokens(result.get("answer", "")):
                    yield ev
                result["reasoning_steps"] = format_reasoning_steps(steps)
                yield {"type": "final", "result": result}
                return

            if not isinstance(routing, dict):
                logger.error("Routing returned unexpected type: %s", type(routing).__name__)
                yield {"type": "final", "result": {
                    "answer": "I encountered an error processing your query. Please try again.",
                    "sources": [],
                    "error": "Internal processing error",
                    "reasoning_steps": format_reasoning_steps(steps),
                }}
                return

            route = routing["route"]
            rewritten_query = routing["rewritten_query"]
            rewrite_info = routing["rewrite_info"]
            metadata_filters = routing["metadata_filters"]
            route_confidence = routing["route_confidence"]
            sub_queries = routing["sub_queries"]

            yield {"type": "status", "status": "routing"}

            remaining_budget_ms = self._remaining_time_ms(start_time)
            final_result = None

            if route == RouteDecision.KNOWLEDGE_BASE:
                handler = self._get_streaming_handler()
                async for event in handler.process_stream(
                    query=rewritten_query,
                    original_query=query,
                    metadata_filters=metadata_filters,
                    steps=steps,
                    timeout_budget_ms=remaining_budget_ms,
                    web_supplement_callback=self.route_processor.supplement_with_web,
                    web_route_callback=self.route_processor.process_web_route,
                    finalize_citations_callback=self.route_processor._finalize_citations,
                    sub_queries=sub_queries,
                    emit_tokens=emit_tokens,
                ):
                    if event.get("type") == "final":
                        final_result = event.get("result", {}) or {}
                    else:
                        yield event

            elif route == RouteDecision.WEB_SEARCH:
                # Web route does not support true token streaming; the full
                # answer is computed synchronously, then chunked for progressive
                # client rendering (see emit_text_as_token_events).
                yield {"type": "status", "status": "searching_web"}
                result = await self.route_processor.process_web_route(
                    rewritten_query,
                    steps,
                    original_query=query,
                    timeout_budget_ms=remaining_budget_ms,
                )
                yield {"type": "status", "status": "generating"}
                async for ev in _emit_answer_tokens(result.get("answer", "")):
                    yield ev
                final_result = result

            else:  # HYBRID
                # Hybrid route does not support true token streaming; the full
                # answer is computed synchronously, then chunked for progressive
                # client rendering (see emit_text_as_token_events).
                yield {"type": "status", "status": "searching_hybrid"}
                result = await self.route_processor.process_hybrid_route(
                    rewritten_query,
                    query,
                    metadata_filters,
                    steps,
                    timeout_budget_ms=remaining_budget_ms,
                )
                yield {"type": "status", "status": "generating"}
                async for ev in _emit_answer_tokens(result.get("answer", "")):
                    yield ev
                final_result = result

            if final_result is None:
                final_result = {"answer": "", "sources": [], "citations": []}

            # Timeout after main processing
            timeout_resp = check_timeout(deadline, start_time, steps, "main processing", query)
            if timeout_resp:
                yield {"type": "final", "result": timeout_resp}
                return

            # Optional validation
            if self.config.enable_validation:
                final_result = await self._validate_answer(final_result, steps)
            else:
                steps.append(AgentStep(
                    name="Answer Validation",
                    status="skipped",
                    details={"reason": "Validation disabled for speed"}
                ))

            # Finalize metadata and citations
            total_time = (time.time() - start_time) * 1000
            timeout_exceeded = (self.config.max_total_time_ms > 0 and
                                total_time > self.config.max_total_time_ms)

            citations = final_result.get("citations", [])
            answer_text = final_result.get("answer", "")

            if final_result.get("_citations_finalized"):
                # Route processor already filtered, suppressed, aligned, and
                # renumbered.  Skip redundant work and go straight to formatting.
                filtered_citations = citations
            else:
                # No finalization callback ran — do it here.
                filtered_citations = self.citation_manager.filter_citations_by_answer(
                    citations, answer_text, query=query
                )
                coverage_score = final_result.get("coverage_score", 1.0)
                if self.citation_manager.should_suppress_citations(
                    query, answer_text, filtered_citations, coverage_score
                ):
                    filtered_citations = []

                # Renumber inline citation markers so their numbers match the
                # filtered citation list. Markers referencing filtered-out
                # sources are removed. Also runs when filtered is empty
                # (suppressed) to strip orphaned markers.
                # Note: this only affects the final result event, not the
                # already-streamed tokens.
                if answer_text and (filtered_citations or citations):
                    renumbered = renumber_citation_markers(answer_text, citations, filtered_citations)
                    if renumbered != answer_text:
                        final_result["answer"] = renumbered

            citation_info = self.citation_manager.format_citations_for_response(
                filtered_citations,
                include_snippets=True
            )

            final_result["metadata"] = {
                "original_query": query,
                "rewritten_query": rewritten_query,
                "route": route.value,
                "route_confidence": route_confidence,
                "total_time_ms": round(total_time, 2),
                "rewrite_info": rewrite_info,
                "timeout_exceeded": timeout_exceeded,
                "timeout_reason": extract_timeout_reason(steps),
                "timing_breakdown": build_timing_breakdown(steps),
                "truncated": final_result.get("truncated", False),
                "kb_empty": final_result.get("kb_empty", False),
            }
            final_result["citations"] = citation_info
            final_result["reasoning_steps"] = format_reasoning_steps(steps)

            # Persist to SQLite cache after the complete reasoning chain is
            # assembled so cache hits are identical to live responses.
            # Fire-and-forget to avoid blocking the final event.
            self._spawn_cache_persist(query, final_result)

            yield {"type": "final", "result": final_result}

        except Exception as e:
            logger.error("Streaming orchestrator error: %s", e, exc_info=True)
            yield {"type": "final", "result": {
                "answer": "I encountered an error processing your query. Please try again.",
                "sources": [],
                "error": "Internal processing error",
                "reasoning_steps": format_reasoning_steps(steps),
            }}
