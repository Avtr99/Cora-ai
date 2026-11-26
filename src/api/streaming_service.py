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
from ..db.chats import answer_id
from ..db.revisions import get_revisions
from ..agents.reasoning_formatter import (
    AgentStep,
    create_timeout_response,
    format_reasoning_steps,
)
from .lifespan import (
    get_gemini_client,
    get_rag_orchestrator,
    get_retriever,
)
from .middleware import ThreatLevel, get_input_sanitizer, get_output_sanitizer, OutputSanitizer
from .query_history import TurnContext, close_turn, is_storable
from .query_models import Query, Response
from .query_sanitization import (
    log_blocked_threat,
    log_output_redaction,
    sanitize_metadata,
    sanitize_quiz_payload,
    sanitize_suggested_prompts,
    sanitize_value,
)


def _sanitize_reasoning_steps(
    formatted_steps: List[Dict[str, Any]],
    output_sanitizer: OutputSanitizer,
    include_duration_ms: bool,
) -> List[Dict[str, Any]]:
    """Sanitize formatted reasoning steps for the wire.

    Shared by the ``result`` payload and terminal ``error`` events so both
    carry identically-shaped partial traces.
    """
    sanitized_steps = []
    for step in formatted_steps:
        sanitized_step = {
            "name": step.get("name") or "unknown",
            "status": step.get("status") or "completed",
            "details": sanitize_value(step.get("details", {}), output_sanitizer),
        }
        if include_duration_ms:
            sanitized_step["duration_ms"] = step.get("duration_ms")
        sanitized_steps.append(sanitized_step)
    return sanitized_steps


def _terminal_error_event(
    message: str,
    *,
    error_id: str,
    steps: List[AgentStep],
    include_reasoning: bool,
    include_duration_ms: bool,
    output_sanitizer: OutputSanitizer,
) -> Dict[str, Any]:
    """Build a terminal SSE error event.

    Attaches the partial reasoning trace (formatted and sanitized exactly like
    the ``result`` path) so the client can show which stage failed.
    """
    event: Dict[str, Any] = {
        "event": "error",
        "error_id": error_id,
        "message": message,
    }
    if include_reasoning and steps:
        sanitized_steps = _sanitize_reasoning_steps(
            format_reasoning_steps(steps), output_sanitizer, include_duration_ms
        )
        if sanitized_steps:
            event["reasoning_steps"] = sanitized_steps
    return event


async def _drain_orchestrator_stream(
    stream_gen: AsyncGenerator[Dict[str, Any], None],
    output_sanitizer: OutputSanitizer,
    final_result_holder: List[Optional[Dict[str, Any]]],
    terminal_error: Optional[List[bool]] = None,
    emit_tokens: bool = True,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Consume orchestrator stream events and yield SSE-formatted dict events.

    Translates the orchestrator's internal ``{"type": ...}`` events into the
    SSE event dicts emitted by the streaming endpoint. The final result, if
    produced, is stored into ``final_result_holder[0]`` so the caller can
    access it after the stream is exhausted. ``{"type": "error"}`` events are
    captured the same way as finals and flagged via ``terminal_error`` so the
    caller can end the stream with an error event.

    Args:
        stream_gen: Async generator from ``rag_orchestrator.process_stream``.
        output_sanitizer: Output sanitizer used to redact token chunks.
        final_result_holder: Single-element list used as a mutable out-param
            for the final result dict.
        terminal_error: Single-element list set to True when the stream ends
            with an internal ``error`` event rather than ``final``.
        emit_tokens: When False, skip ``token`` and ``replace`` events (the
            orchestrator still consumes its internal stream to produce the
            ``final`` result, but no token events are forwarded to the client).

    Yields:
        SSE-formatted event dicts (``status``/``replace``/``token``).
    """
    async for event in stream_gen:
        etype = event.get("type")
        if etype == "status":
            yield {"event": "status", "status": event.get("status", "processing")}
        elif etype == "replace":
            if emit_tokens:
                yield {"event": "replace"}
        elif etype == "token":
            if emit_tokens:
                chunk = str(event.get("chunk", "") or "")
                sanitized_chunk, _ = output_sanitizer.sanitize(chunk)
                if sanitized_chunk:
                    yield {"event": "token", "chunk": sanitized_chunk}
        elif etype in ("final", "error"):
            final_result_holder[0] = event.get("result", {}) or {}
            if terminal_error is not None:
                terminal_error[0] = etype == "error"


async def process_query_core_stream(
    query: Query,
    request: Request,
    ctx: TurnContext,
    *,
    include_reasoning: bool,
    include_metadata: bool,
    include_duration_ms: bool,
    emit_tokens: bool = True,
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

    When ``emit_tokens`` is False, ``token`` and ``replace`` events are
    suppressed — the orchestrator still runs its full pipeline (including
    streaming LLM generation internally) but only ``status``/``result``/
    ``done``/``error`` events are forwarded. This is used by clients that
    only need status progress + the final answer (e.g. the web UI, which
    renders the complete answer on ``result`` rather than streaming tokens).
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

    # Capture the config generation at request start. This is an observability
    # stamp, not a consistency guarantee: later stages may read a newer config if
    # a settings save happens mid-request.
    config_version = get_revisions().get("config_version", 0)

    retriever = get_retriever()
    gemini_client = get_gemini_client()
    rag_orchestrator = get_rag_orchestrator()

    if retriever is None or gemini_client is None or rag_orchestrator is None:
        logger.warning("Service still initializing or LLM not configured during streaming query")
        error_id = str(uuid.uuid4())[:8]
        yield {"event": "error", "error_id": error_id,
               "message": "Service initializing or LLM not configured. Visit /setup to configure."}
        return

    settings = get_settings()
    timeout_ms = max(float(getattr(settings, "RAG_TIMEOUT_MS", 0) or 0), 0.0)
    timeout_seconds = timeout_ms / 1000.0

    orchestrator_kwargs: Dict[str, Any] = {
        "query": safe_query,
        "metadata_filters": None,
    }
    if ctx.history:
        orchestrator_kwargs["chat_history"] = [
            {"role": m.role, "content": m.content} for m in ctx.history
        ]

    output_sanitizer = get_output_sanitizer()
    final_result: Optional[Dict[str, Any]] = None

    # Caller-owned step list: the orchestrator appends pipeline steps as they
    # complete, so a terminal error event or exception can still carry the
    # partial trace.
    steps: List[AgentStep] = []
    stream_gen = rag_orchestrator.process_stream(
        emit_tokens=emit_tokens, steps=steps, **orchestrator_kwargs
    )
    final_result_holder: List[Optional[Dict[str, Any]]] = [None]
    terminal_error = [False]
    try:
        if timeout_seconds > 0:
            async with asyncio.timeout(timeout_seconds):
                async for sse_event in _drain_orchestrator_stream(
                    stream_gen, output_sanitizer, final_result_holder,
                    terminal_error, emit_tokens=emit_tokens,
                ):
                    yield sse_event
        else:
            async for sse_event in _drain_orchestrator_stream(
                stream_gen, output_sanitizer, final_result_holder,
                terminal_error, emit_tokens=emit_tokens,
            ):
                yield sse_event
        final_result = final_result_holder[0]

    except TimeoutError:
        logger.warning("Streaming query hard timeout reached", extra={"timeout_ms": timeout_ms})
        # Backstop for when the outer asyncio.timeout fires before the
        # orchestrator's own check_timeout emits a final event with steps.
        final_result = create_timeout_response(
            safe_query,
            steps=steps,
            total_time_ms=timeout_ms,
        )
    except asyncio.CancelledError:
        logger.info("Streaming query cancelled by client disconnect")
        return
    except Exception as e:
        error_id = str(uuid.uuid4())[:8]
        logger.exception(f"Error processing streaming query [error_id={error_id}]: {e}")
        yield _terminal_error_event(
            "Internal server error processing query",
            error_id=error_id,
            steps=steps,
            include_reasoning=include_reasoning,
            include_duration_ms=include_duration_ms,
            output_sanitizer=output_sanitizer,
        )
        return
    finally:
        await stream_gen.aclose()

    if terminal_error[0]:
        # The orchestrator classified this result as a handled failure. Surface
        # it as an error event carrying the sanitized answer text and trace.
        error_id = str(uuid.uuid4())[:8]
        logger.warning(f"Streaming query ended with a terminal error result [error_id={error_id}]")
        error_answer = str((final_result or {}).get("answer") or "")
        sanitized_error_answer, error_redacted = (
            output_sanitizer.sanitize(error_answer) if error_answer else ("", [])
        )
        log_output_redaction(request, error_redacted)
        yield _terminal_error_event(
            sanitized_error_answer or "Internal server error processing query",
            error_id=error_id,
            steps=steps,
            include_reasoning=include_reasoning,
            include_duration_ms=include_duration_ms,
            output_sanitizer=output_sanitizer,
        )
        return

    if final_result is None:
        # The stream ended without a final result — a failure, not an empty
        # answer. Storing it would persist a blank turn as if it succeeded.
        error_id = str(uuid.uuid4())[:8]
        logger.warning(f"Streaming query ended with no result [error_id={error_id}]")
        yield _terminal_error_event(
            "Internal server error processing query",
            error_id=error_id,
            steps=steps,
            include_reasoning=include_reasoning,
            include_duration_ms=include_duration_ms,
            output_sanitizer=output_sanitizer,
        )
        return

    answer = str(final_result.get("answer", "") or "")
    sanitized_answer, redacted_items = output_sanitizer.sanitize(answer)
    log_output_redaction(request, redacted_items)

    sources = final_result.get("sources") or ["knowledge_base"]
    sanitized_sources = sanitize_value(sources, output_sanitizer)
    safe_sources = [str(s) for s in sanitized_sources if s] or ["knowledge_base"]

    sanitized_metadata = None
    if include_metadata:
        raw_metadata = final_result.get("metadata") or {}
        sanitized_metadata = sanitize_metadata(
            raw_metadata,
            output_sanitizer,
            config_version=config_version,
        )

    sanitized_reasoning_steps = None
    if include_reasoning and final_result.get("reasoning_steps"):
        sanitized_reasoning_steps = _sanitize_reasoning_steps(
            final_result["reasoning_steps"], output_sanitizer, include_duration_ms
        )

    response = Response(
        answer=sanitized_answer,
        confidence=final_result.get("confidence", 0.0),
        sources=safe_sources,
        conversation_id=ctx.conversation_id,
        message_id=ctx.message_id,
        answer_id=answer_id(ctx.message_id),
        timestamp=datetime.now(timezone.utc).isoformat(),
        citations=final_result.get("citations"),
        reasoning_steps=sanitized_reasoning_steps,
        metadata=sanitized_metadata,
        quiz=sanitize_quiz_payload(final_result.get("quiz"), output_sanitizer),
        suggested_prompts=sanitize_suggested_prompts(
            final_result.get("suggested_prompts"), output_sanitizer
        ),
        truncated=final_result.get("truncated", False),
        error_fallback=not is_storable(final_result),
        config_version=config_version,
    )

    # Store the turn just before the result event: a client that leaves
    # earlier stores nothing; one that leaves after still gets a stored turn.
    await close_turn(ctx, query.text, response)

    payload = response.model_dump() if hasattr(response, "model_dump") else dict(response)
    yield {"event": "result", "payload": payload}
    yield {"event": "done"}
