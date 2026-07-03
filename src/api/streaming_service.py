"""Streaming query processing service used by the SSE endpoints.

This module is separate from ``query_service.py`` so the non-streaming pipeline
stays unchanged. It mirrors the same security, history, and sanitization
behavior while emitting dict events that the API layer formats as SSE.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, AsyncGenerator

from fastapi import Request
from loguru import logger

from ..config import get_settings
from ..agents.reasoning_formatter import create_timeout_response
from .lifespan import (
    get_gemini_client,
    get_rag_orchestrator,
    get_retriever,
)
from .middleware import ThreatLevel, get_input_sanitizer, get_output_sanitizer, OutputSanitizer
from .query_history import sanitize_history_messages
from .query_models import Message, Query, Response
from .query_sanitization import (
    log_blocked_threat,
    log_output_redaction,
    sanitize_metadata,
    sanitize_quiz_payload,
    sanitize_suggested_prompts,
    sanitize_value,
)
from ..utils.security import sign_history, verify_history_signature

HISTORY_CONTEXT_MAX_MESSAGES = 10


async def _drain_orchestrator_stream(
    stream_gen: AsyncGenerator[Dict[str, Any], None],
    output_sanitizer: OutputSanitizer,
    final_result_holder: List[Optional[Dict[str, Any]]],
) -> AsyncGenerator[Dict[str, Any], None]:
    """Consume orchestrator stream events and yield SSE-formatted dict events.

    Translates the orchestrator's internal ``{"type": ...}`` events into the
    SSE event dicts emitted by the streaming endpoint. The final result, if
    produced, is stored into ``final_result_holder[0]`` so the caller can
    access it after the stream is exhausted.

    Args:
        stream_gen: Async generator from ``rag_orchestrator.process_stream``.
        output_sanitizer: Output sanitizer used to redact token chunks.
        final_result_holder: Single-element list used as a mutable out-param
            for the final result dict.

    Yields:
        SSE-formatted event dicts (``status``/``replace``/``token``).
    """
    async for event in stream_gen:
        if event.get("type") == "status":
            yield {"event": "status", "status": event.get("status", "processing")}
        elif event.get("type") == "replace":
            yield {"event": "replace"}
        elif event.get("type") == "token":
            chunk = str(event.get("chunk", "") or "")
            sanitized_chunk, _ = output_sanitizer.sanitize(chunk)
            if sanitized_chunk:
                yield {"event": "token", "chunk": sanitized_chunk}
        elif event.get("type") == "final":
            final_result_holder[0] = event.get("result", {}) or {}


async def process_query_core_stream(
    query: Query,
    request: Request,
    *,
    include_reasoning: bool,
    include_metadata: bool,
    include_duration_ms: bool,
    include_chat_history_in_orchestrator: bool,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Shared streaming query pipeline used by ``/query/stream``.

    Yields dict events:

    - ``{"event": "status", "status": "..."}``
    - ``{"event": "replace"}`` -- client should clear any buffered token text
    - ``{"event": "token", "chunk": "..."}``
    - ``{"event": "result", "payload": {...}}``
    - ``{"event": "done"}``
    - ``{"event": "error", "error_id": ..., "message": ...}``

    The ``replace`` event is emitted when the KB answer is supplemented with a
    web answer: the client must discard previously rendered token text and
    render the subsequent token(s) fresh.
    """

    input_sanitizer = get_input_sanitizer()
    sanitization_result = input_sanitizer.sanitize(query.text)

    if sanitization_result.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
        log_blocked_threat(
            sanitization_result.threats_detected,
            sanitization_result.threat_level,
            context="query",
        )
        error_id = str(uuid.uuid4())[:8]
        yield {"event": "error", "error_id": error_id,
               "message": "Query contains potentially harmful content and was blocked for security reasons."}
        return

    safe_query = sanitization_result.sanitized_text

    retriever = get_retriever()
    gemini_client = get_gemini_client()
    rag_orchestrator = get_rag_orchestrator()

    if retriever is None or gemini_client is None or rag_orchestrator is None:
        logger.warning("Service still initializing or LLM not configured during streaming query")
        error_id = str(uuid.uuid4())[:8]
        yield {"event": "error", "error_id": error_id,
               "message": "Service initializing or LLM not configured. Visit /setup to configure."}
        return

    history_scope_key = None
    settings = get_settings()
    signing_secret = settings.SECRET_KEY
    timeout_ms = max(float(getattr(settings, "RAG_TIMEOUT_MS", 0) or 0), 0.0)
    timeout_seconds = timeout_ms / 1000.0

    if not signing_secret:
        logger.warning("History signing secret not configured. History integrity checks skipped.")
        history_verified = True
    else:
        history_verified = False

    original_history_present = bool(query.history)
    trusted_history: Optional[List[Message]] = query.history

    if trusted_history and query.conversation_id:
        if signing_secret and query.history_signature:
            history_list = [{"role": m.role, "content": m.content} for m in trusted_history]
            if verify_history_signature(
                history_list,
                query.conversation_id,
                query.history_signature,
                signing_secret,
                scope_key=history_scope_key or "",
            ):
                history_verified = True
                logger.debug(f"History signature verified for conversation {query.conversation_id}")
            else:
                logger.warning(
                    f"History signature verification FAILED for conversation {query.conversation_id}."
                )
                trusted_history = None
                history_verified = False
        elif not signing_secret:
            pass
        elif not history_scope_key:
            if query.history_signature is None:
                logger.warning("History provided for anonymous request without signature. Discarding.")
                history_verified = False
                trusted_history = None
    elif trusted_history and not query.conversation_id:
        logger.warning("History provided without conversation_id. Discarding.")
        history_verified = False
        trusted_history = None

    history_window = trusted_history[-HISTORY_CONTEXT_MAX_MESSAGES:] if trusted_history else None
    cleaned_history = sanitize_history_messages(history_window)
    scoped_history = cleaned_history

    input_history_len = len(history_window) if history_window else 0
    history_items_dropped = input_history_len - len(cleaned_history)

    orchestrator_kwargs: Dict[str, Any] = {
        "query": safe_query,
        "metadata_filters": None,
    }
    if include_chat_history_in_orchestrator and scoped_history:
        orchestrator_kwargs["chat_history"] = [{"role": m.role, "content": m.content} for m in scoped_history]

    output_sanitizer = get_output_sanitizer()
    final_result: Optional[Dict[str, Any]] = None

    stream_gen = rag_orchestrator.process_stream(**orchestrator_kwargs)
    final_result_holder: List[Optional[Dict[str, Any]]] = [None]
    try:
        if timeout_seconds > 0:
            async with asyncio.timeout(timeout_seconds):
                async for sse_event in _drain_orchestrator_stream(
                    stream_gen, output_sanitizer, final_result_holder
                ):
                    yield sse_event
        else:
            async for sse_event in _drain_orchestrator_stream(
                stream_gen, output_sanitizer, final_result_holder
            ):
                yield sse_event
        final_result = final_result_holder[0]

    except TimeoutError:
        logger.warning("Streaming query hard timeout reached", extra={"timeout_ms": timeout_ms})
        # steps=[] is intentional: the orchestrator's internal step list is
        # not accessible at this scope.  The orchestrator's own check_timeout
        # normally catches timeouts first and emits a final event with steps;
        # this is only the degenerate backstop when the outer asyncio.timeout
        # fires before the inner check runs.
        final_result = create_timeout_response(
            safe_query,
            steps=[],
            total_time_ms=timeout_ms,
        )
    except asyncio.CancelledError:
        logger.info("Streaming query cancelled by client disconnect")
        return
    except Exception as e:
        error_id = str(uuid.uuid4())[:8]
        logger.exception(f"Error processing streaming query [error_id={error_id}]: {e}")
        yield {"event": "error", "error_id": error_id,
               "message": "Internal server error processing query"}
        return
    finally:
        await stream_gen.aclose()

    if final_result is None:
        final_result = {"answer": "", "sources": ["knowledge_base"], "citations": None}

    answer = str(final_result.get("answer", "") or "")
    sanitized_answer, redacted_items = output_sanitizer.sanitize(answer)
    log_output_redaction(request, redacted_items)

    sources = final_result.get("sources") or ["knowledge_base"]
    sanitized_sources = sanitize_value(sources, output_sanitizer)
    safe_sources = [str(s) for s in sanitized_sources if s] or ["knowledge_base"]

    conversation_id = query.conversation_id or str(uuid.uuid4())
    new_history = []
    if scoped_history:
        new_history.extend([{"role": m.role, "content": m.content} for m in scoped_history])
    new_history.append({"role": "user", "content": safe_query})
    new_history.append({"role": "assistant", "content": sanitized_answer})
    new_history = new_history[-HISTORY_CONTEXT_MAX_MESSAGES:]

    if signing_secret:
        history_signature = sign_history(
            new_history,
            conversation_id,
            signing_secret,
            scope_key=history_scope_key or "",
            allow_unsigned=False,
        )
    else:
        history_signature = None

    sanitized_metadata = None
    history_signals_triggered = history_items_dropped > 0 or (
        history_verified is False and original_history_present
    )
    if include_metadata or history_signals_triggered:
        raw_metadata = final_result.get("metadata") or {}
        sanitized_metadata = sanitize_metadata(
            raw_metadata,
            output_sanitizer,
            history_verification_failed=original_history_present and not history_verified,
            history_items_dropped=history_items_dropped,
        )

    sanitized_reasoning_steps = None
    if include_reasoning and final_result.get("reasoning_steps"):
        sanitized_reasoning_steps = []
        for step in final_result["reasoning_steps"]:
            sanitized_step = {
                "name": step.get("name") or "unknown",
                "status": step.get("status") or "completed",
                "details": sanitize_value(step.get("details", {}), output_sanitizer),
            }
            if include_duration_ms:
                sanitized_step["duration_ms"] = step.get("duration_ms")
            sanitized_reasoning_steps.append(sanitized_step)

    response = Response(
        answer=sanitized_answer,
        confidence=final_result.get("confidence", 0.0),
        sources=safe_sources,
        conversation_id=conversation_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        citations=final_result.get("citations"),
        reasoning_steps=sanitized_reasoning_steps,
        metadata=sanitized_metadata,
        quiz=sanitize_quiz_payload(final_result.get("quiz"), output_sanitizer),
        suggested_prompts=sanitize_suggested_prompts(
            final_result.get("suggested_prompts"), output_sanitizer
        ),
        history_signature=history_signature,
        truncated=final_result.get("truncated", False),
    )

    payload = response.model_dump() if hasattr(response, "model_dump") else dict(response)
    yield {"event": "result", "payload": payload}
    yield {"event": "done"}
