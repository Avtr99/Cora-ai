"""Shared query processing service used by API entry points."""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import HTTPException, Request
from loguru import logger

from ..config import get_settings
from ..db.chats import answer_id
from ..db.revisions import get_revisions
from ..citations.context import citations_from_result
from ..query_processing.filter_extractor import extract_filters
from ..agents.reasoning_formatter import create_timeout_response
from .lifespan import (
    get_citation_manager,
    get_gemini_client,
    get_rag_orchestrator,
    get_retriever,
)
from .middleware import ThreatLevel, get_input_sanitizer, get_output_sanitizer
from .query_history import TurnContext, close_turn, format_history_string
from .query_models import Query, Response
from .query_sanitization import (
    log_blocked_threat,
    log_output_redaction,
    sanitize_metadata,
    sanitize_quiz_payload,
    sanitize_suggested_prompts,
    sanitize_value,
)


async def process_query_core(
    query: Query,
    request: Request,
    ctx: TurnContext,
    *,
    include_reasoning: bool,
    include_metadata: bool,
    include_duration_ms: bool,
) -> Response:
    """Shared query pipeline used by both API entry points."""

    input_sanitizer = get_input_sanitizer()
    sanitization_result = input_sanitizer.sanitize(query.text)

    if sanitization_result.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
        log_blocked_threat(
            sanitization_result.threats_detected,
            sanitization_result.threat_level,
            context="query",
        )
        raise HTTPException(
            status_code=400,
            detail="Query contains potentially harmful content and was blocked for security reasons.",
        )

    safe_query = sanitization_result.sanitized_text

    # Capture the config generation at request start. This is an observability
    # stamp, not a consistency guarantee: later stages may read a newer config if
    # a settings save happens mid-request.
    config_version = get_revisions().get("config_version", 0)

    retriever = get_retriever()
    gemini_client = get_gemini_client()
    rag_orchestrator = get_rag_orchestrator()
    citation_manager = get_citation_manager()

    if retriever is None:
        logger.warning("Retriever not initialized - service still starting up")
        raise HTTPException(status_code=503, detail="Service initializing, please retry shortly")

    if gemini_client is None:
        logger.warning("LLM client not initialized - service still starting up or not configured")
        raise HTTPException(status_code=503, detail="Service initializing or LLM not configured. Visit /setup to configure.")

    settings = get_settings()
    timeout_ms = max(float(getattr(settings, "RAG_TIMEOUT_MS", 0) or 0), 0.0)
    timeout_seconds = timeout_ms / 1000.0

    if rag_orchestrator is not None:
        logger.debug("Using multi-agent RAG orchestrator")

        # Orchestrator handles filter extraction internally to ensure
        # extracted filters take precedence over rewritten ones correctly.
        orchestrator_kwargs: Dict[str, Any] = {
            "query": safe_query,
            "metadata_filters": None,
        }

        if ctx.history:
            orchestrator_kwargs["chat_history"] = [
                {"role": m.role, "content": m.content} for m in ctx.history
            ]

        try:
            if timeout_seconds > 0:
                async with asyncio.timeout(timeout_seconds):
                    processed_results = await rag_orchestrator.process(**orchestrator_kwargs)
            else:
                processed_results = await rag_orchestrator.process(**orchestrator_kwargs)
        except TimeoutError:
            logger.warning(
                "Hard timeout reached while waiting for rag_orchestrator",
                extra={"timeout_ms": timeout_ms},
            )
            processed_results = create_timeout_response(
                safe_query,
                steps=[],
                total_time_ms=timeout_ms,
            )
    else:
        logger.debug("Using legacy RAG pipeline (orchestrator not available)")

        # Legacy Pipeline: Manual filter extraction and history formatting
        cleaned_query, metadata_filters = extract_filters(safe_query)
        
        if metadata_filters:
            logger.debug(f"Extracted filters: {metadata_filters}, cleaned query: '{cleaned_query}'")

        if ctx.history:
            history_context = format_history_string(ctx.history)
            contextual_query = (
                "Conversation history (context only):\n"
                f"{history_context}\n\n"
                f"User query: {safe_query}"
            )
        else:
            contextual_query = safe_query

        query_text = cleaned_query if metadata_filters else safe_query
        vector_results = await retriever.retrieve(
            query=query_text,
            where=metadata_filters,
        )

        processed_results = await gemini_client.search_and_process(
            query=contextual_query,
            vector_results=vector_results,
        )

        if citation_manager:
            # Same canonical source records the prompt numbered — select the
            # cited subset (and strip invalid markers) via finalize.
            processed_results["citations"] = citations_from_result(processed_results)
            citation_manager.finalize(
                processed_results,
                safe_query,
                processed_results.get("coverage_score", 1.0),
            )
            citation_info = citation_manager.format_citations_for_response(
                processed_results["citations"],
                include_snippets=True,
            )
            processed_results["citations"] = citation_info

    output_sanitizer = get_output_sanitizer()
    sanitized_answer, redacted_items = output_sanitizer.sanitize(processed_results["answer"])

    sanitized_reasoning_steps = None
    if include_reasoning and processed_results.get("reasoning_steps"):
        sanitized_reasoning_steps = []
        for step in processed_results["reasoning_steps"]:
            sanitized_step = {
                "name": step.get("name") or "unknown",
                "status": step.get("status") or "completed",
                "details": sanitize_value(step.get("details", {}), output_sanitizer),
            }
            if include_duration_ms:
                sanitized_step["duration_ms"] = step.get("duration_ms")
            sanitized_reasoning_steps.append(sanitized_step)

    log_output_redaction(request, redacted_items)

    sanitized_sources = sanitize_value(
        processed_results.get("sources") or ["knowledge_base"],
        output_sanitizer,
    )
    safe_sources = [str(s) for s in sanitized_sources if s] or ["knowledge_base"]

    sanitized_metadata = None
    if include_metadata:
        raw_metadata = processed_results.get("metadata") or {}
        sanitized_metadata = sanitize_metadata(
            raw_metadata,
            output_sanitizer,
            config_version=config_version,
        )

    sanitized_quiz = sanitize_quiz_payload(processed_results.get("quiz"), output_sanitizer)
    sanitized_suggested_prompts = sanitize_suggested_prompts(
        processed_results.get("suggested_prompts"), output_sanitizer
    )

    response = Response(
        answer=sanitized_answer,
        confidence=processed_results.get("confidence", 0.0),
        sources=safe_sources,
        conversation_id=ctx.conversation_id,
        message_id=ctx.message_id,
        answer_id=answer_id(ctx.message_id),
        timestamp=datetime.now(timezone.utc).isoformat(),
        citations=processed_results.get("citations"),
        reasoning_steps=sanitized_reasoning_steps,
        metadata=sanitized_metadata,
        quiz=sanitized_quiz,
        suggested_prompts=sanitized_suggested_prompts,
        truncated=processed_results.get("truncated", False),
        config_version=config_version,
    )

    # Store the turn from the raw result's failure shape, not the
    # sanitized response. ChatNotFound propagates.
    await close_turn(ctx, query.text, response, processed_results)

    return response
