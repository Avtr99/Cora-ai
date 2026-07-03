"""Streaming knowledge-base route handler.

This handler is intentionally separate from ``kb_route_handler.py`` so that the
existing KB route handler remains unchanged and the streaming path stays
isolated and easy to reason about.
"""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional, AsyncGenerator

from .reasoning_formatter import AgentStep
from .route_processor_utils import (
    check_answer_relevance,
    clean_source_display_name,
    emit_text_as_token_events,
    extract_source_titles,
    kb_top_relevance,
    remaining_budget_ms,
    source_name_from_metadata,
    try_serve_cached_answer,
)
from ..citations import CitationManager
from ..query_processing.fallback_answers import is_non_answer

logger = logging.getLogger(__name__)

# Characters of generated text to buffer before deciding whether the KB answer
# is a non-answer fallback. The known non-answer prefixes are ~60 chars, so a
# small buffer lets us suppress them (and fall back to web) WITHOUT first
# flashing the "information not found" text to the client.
_NON_ANSWER_GATE_CHARS = 80


def _is_explicit_non_answer(answer: str) -> bool:
    """Return whether answer text is an explicit KB non-answer fallback.

    Thin wrapper around :func:`src.query_processing.fallback_answers.is_non_answer`
    kept for backwards compatibility with internal call sites.
    """
    return is_non_answer(answer)


class KBStreamingHandler:
    """Handle KB route with true token streaming for answer generation."""

    def __init__(
        self,
        retriever: Any,
        answer_generator: Any,
        citation_manager: CitationManager,
        config: Any,
        validator: Optional[Any] = None,
    ):
        """Initialize the streaming KB handler.

        Args:
            retriever: Object implementing ``retrieve(query, where)``.
            answer_generator: Object implementing ``search_and_process_stream``.
            citation_manager: CitationManager instance.
            config: OrchestratorConfig instance.
            validator: Optional relevance checker implementing check_relevance().
        """
        self.retriever = retriever
        self.answer_generator = answer_generator
        self.citation_manager = citation_manager
        self.config = config
        self.validator = validator

    async def process_stream(
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
        emit_tokens: bool = True,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream-process a KB query.

        Yields ``{"type": "status", "status": "..."}``, token events, and a
        final ``{"type": "final", "result": {...}}`` event. If the answer is
        insufficient or no KB documents are found, the handler may fall back to
        web search and emit the final answer as a single token.

        When ``emit_tokens`` is False, token events are suppressed — the
        handler still runs the full pipeline (retrieval, generation, relevance
        checks, fallbacks) and yields ``status`` + ``final`` events, but no
        ``token`` events. This skips the non-answer buffer gate entirely (no
        need to hold tokens for inspection when they won't be emitted).
        """
        step_start = time.time()

        async def _emit_tokens(text: str) -> AsyncGenerator[Dict[str, Any], None]:
            """Yield token events for a pre-computed answer, unless suppressed."""
            if emit_tokens:
                async for ev in emit_text_as_token_events(text):
                    yield ev

        try:
            if sub_queries and hasattr(self.retriever, "retrieve_with_fusion"):
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
            logger.error("Error during streaming KB retrieval: %s", e, exc_info=True)
            vector_results = {"documents": [], "metadatas": [], "ids": [], "distances": []}

        retrieval_duration = (time.time() - step_start) * 1000
        doc_count = len(vector_results.get("documents", []))
        doc_highlights = self._extract_doc_highlights(vector_results, max_highlights=6)

        steps.append(AgentStep(
            name="Knowledge Base Retrieval",
            status="completed",
            duration_ms=round(retrieval_duration, 2),
            details={
                "documents_retrieved": doc_count,
                "threshold": getattr(self.config, "retrieval_threshold", 0.0),
                "highlights": doc_highlights,
            }
        ))

        yield {"type": "status", "status": "retrieving", "details": {"documents_retrieved": doc_count}}

        # Fall back to web BEFORE generation when the KB has no results OR
        # nothing confidently relevant. This matches the non-streaming KB
        # path's pre-generation gate and avoids both wrong KB answers and the
        # "information not found" flash.
        top_relevance = kb_top_relevance(vector_results)
        kb_min_top = float(getattr(self.config, "kb_min_top_relevance_score", 0.0) or 0.0)
        kb_not_confident = doc_count > 0 and kb_min_top > 0 and top_relevance < kb_min_top
        web_enabled = getattr(self.config, "enable_web_search", False)

        if (doc_count == 0 or kb_not_confident) and web_enabled and web_route_callback:
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
                cached_answer = str(cached_result.get("answer", "") or "")
                yield {"type": "status", "status": "generating"}
                async for ev in _emit_tokens(cached_answer):
                    yield ev
                yield {"type": "final", "result": cached_result}
                return

            if doc_count == 0:
                reason = "No KB results, using web search"
            else:
                reason = (
                    f"KB relevance too low (top={top_relevance:.2f} < "
                    f"{kb_min_top:.2f}), using web search"
                )
            logger.info("Streaming path falling back to web search: %s", reason)
            steps.append(AgentStep(
                name="Fallback Decision",
                status="completed",
                details={"reason": reason}
            ))
            remaining = remaining_budget_ms(timeout_budget_ms, step_start)
            web_result = await web_route_callback(
                query,
                steps,
                original_query=original_query,
                timeout_budget_ms=remaining,
            )
            yield {"type": "status", "status": "generating"}
            async for ev in _emit_tokens(web_result.get("answer", "")):
                yield ev
            yield {"type": "final", "result": web_result}
            return

        gen_start = time.time()
        yield {"type": "status", "status": "generating"}

        stream_method = getattr(self.answer_generator, "search_and_process_stream", None)
        if stream_method is None:
            logger.warning("answer_generator does not implement search_and_process_stream; using fallback")
            try:
                result = await self.answer_generator.search_and_process(original_query, vector_results)
            except Exception as e:
                duration = (time.time() - gen_start) * 1000
                logger.error("Answer generation failed in streaming path: %s", e, exc_info=True)
                error_id = str(uuid.uuid4())[:8]
                steps.append(AgentStep(
                    name="Answer Generation",
                    status="failed",
                    duration_ms=round(duration, 2),
                    details={"error": "internal_error", "error_id": error_id, "source": "knowledge_base"}
                ))
                yield {"type": "final", "result": {
                    "answer": "I encountered an error generating the answer. Please try again.",
                    "sources": ["error_fallback"],
                    "citations": None,
                    "confidence": 0.0,
                }}
                return

            # Post-generation handling: mirror the sync KB path.
            # 1) If the answer is an explicit non-answer fallback, supplement
            #    with web (same as sync path's _check_supplementation_needed).
            # 2) If the answer passes the non-answer check, run the LLM
            #    relevance check. If it fails, fall back to web-only.
            answer_text = result.get("answer", "")

            # Non-answer fallback → supplement with web
            if _is_explicit_non_answer(answer_text) and web_enabled and web_supplement_callback:
                logger.info("Streaming KB (non-stream fallback) returned non-answer; supplementing with web")
                remaining = remaining_budget_ms(timeout_budget_ms, step_start)
                web_result = await web_supplement_callback(
                    query,
                    result,
                    vector_results,
                    steps,
                    supplement_reason="KB returned non-answer fallback",
                    timeout_budget_ms=remaining,
                )
                gen_duration = (time.time() - gen_start) * 1000
                steps.append(AgentStep(
                    name="Answer Generation",
                    status="completed",
                    duration_ms=round(gen_duration, 2),
                    details={"source": "web_supplement", "summary": web_result.get("answer", "")[:150]}
                ))
                async for ev in _emit_tokens(web_result.get("answer", "")):
                    yield ev
                yield {"type": "final", "result": web_result}
                return

            # Relevance check for non-non-answer results
            if (
                self.validator
                and web_enabled
                and web_route_callback
                and not _is_explicit_non_answer(answer_text)
            ):
                is_irrelevant, reason = await check_answer_relevance(
                    self.validator, self.config,
                    original_query, answer_text, log_tag="Streaming",
                    source_titles=extract_source_titles(vector_results),
                )
                if is_irrelevant:
                    remaining = remaining_budget_ms(timeout_budget_ms, step_start)
                    web_result = await web_route_callback(
                        query,
                        steps,
                        original_query=original_query,
                        timeout_budget_ms=remaining,
                    )
                    async for ev in _emit_tokens(web_result.get("answer", "")):
                        yield ev
                    yield {"type": "final", "result": web_result}
                    return

            gen_duration = (time.time() - gen_start) * 1000
            answer_summary = answer_text[:150] if answer_text else ""
            steps.append(AgentStep(
                name="Answer Generation",
                status="completed",
                duration_ms=round(gen_duration, 2),
                details={"source": "knowledge_base", "summary": answer_summary}
            ))

            async for ev in _emit_tokens(answer_text):
                yield ev
            yield {"type": "final", "result": result}
            return

        # Consume the LLM stream to obtain the final result. When emit_tokens
        # is True, buffer-gate the first ~80 chars to detect non-answer
        # fallbacks before forwarding tokens to the client (prevents flashing
        # "information not found" text). When emit_tokens is False, drain
        # silently — no token events are forwarded regardless.
        result = None
        buffered = ""
        gate_open = False
        try:
            async for event in stream_method(original_query, vector_results):
                etype = event.get("type")
                if etype == "token":
                    if not emit_tokens:
                        # Silently drain; only the final result matters.
                        continue
                    if gate_open:
                        yield event
                        continue
                    buffered += str(event.get("chunk", "") or "")
                    if len(buffered.strip()) >= _NON_ANSWER_GATE_CHARS:
                        if _is_explicit_non_answer(buffered):
                            # Keep draining silently to obtain the final result;
                            # do not forward these tokens to the client.
                            continue
                        gate_open = True
                        yield {"type": "token", "chunk": buffered}
                        buffered = ""
                elif etype == "final":
                    result = event.get("result", {}) or {}
                    break
        except Exception as e:
            duration = (time.time() - gen_start) * 1000
            logger.error("Streaming answer generation failed: %s", e, exc_info=True)
            error_id = str(uuid.uuid4())[:8]
            steps.append(AgentStep(
                name="Answer Generation",
                status="failed",
                duration_ms=round(duration, 2),
                details={"error": "internal_error", "error_id": error_id, "source": "knowledge_base"}
            ))
            yield {"type": "final", "result": {
                "answer": "I encountered an error generating the answer. Please try again.",
                "sources": ["error_fallback"],
                "citations": None,
                "confidence": 0.0,
            }}
            return

        gen_duration = (time.time() - gen_start) * 1000
        answer_text = result.get("answer", "") if result else ""
        answer_summary = answer_text[:150] if answer_text else ""
        steps.append(AgentStep(
            name="Answer Generation",
            status="completed",
            duration_ms=round(gen_duration, 2),
            details={"source": "knowledge_base", "summary": answer_summary}
        ))

        # If the stream was a non-answer fallback and web is enabled, supplement
        # with web instead of returning the fallback.
        if _is_explicit_non_answer(buffered) and web_enabled and web_supplement_callback:
            logger.info("Streaming KB returned non-answer fallback; supplementing with web search")
            remaining = remaining_budget_ms(timeout_budget_ms, step_start)
            web_result = await web_supplement_callback(
                query,
                result or {},
                vector_results,
                steps,
                supplement_reason="KB returned non-answer fallback",
                timeout_budget_ms=remaining,
            )
            async for ev in _emit_tokens(web_result.get("answer", "")):
                yield ev
            yield {"type": "final", "result": web_result}
            return

        if emit_tokens and buffered and not gate_open:
            yield {"type": "token", "chunk": buffered}

        # Finalize and emit citations
        final_result = result or {}
        if finalize_citations_callback:
            try:
                finalize_citations_callback(final_result, original_query)
            except Exception as e:
                logger.warning("Citation finalization failed in streaming handler: %s", e)

        yield {"type": "final", "result": final_result}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_doc_highlights(
        self,
        vector_results: Dict[str, Any],
        max_highlights: int = 2,
    ) -> List[str]:
        """Extract short snippet highlights from top documents."""
        highlights = []
        documents = vector_results.get("documents", []) or []
        metadatas = vector_results.get("metadatas", []) or []
        for idx, doc in enumerate(documents[:max_highlights]):
            if not doc:
                continue
            metadata = metadatas[idx] if idx < len(metadatas) else {}
            snippet = doc[:120].replace("\n", " ").strip()
            source_name = source_name_from_metadata(metadata)
            if source_name:
                highlights.append(f"{source_name}: {snippet}")
            else:
                highlights.append(snippet)
        return highlights

    def _format_sources(self, vector_results: Dict[str, Any]) -> List[str]:
        """Build a clean source list from retrieved chunk metadata."""
        sources = []
        metadatas = vector_results.get("metadatas", []) or []
        for metadata in metadatas:
            source_name = source_name_from_metadata(metadata)
            if source_name:
                cleaned = clean_source_display_name(source_name)
                if cleaned and cleaned not in sources:
                    sources.append(cleaned)
        return sources
