"""Shared query processing service used by API entry points."""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Request
from loguru import logger

from ..config import get_settings
from ..query_processing.filter_extractor import extract_filters
from ..utils.security import sign_history, verify_history_signature
from ..agents.reasoning_formatter import create_timeout_response
from .lifespan import (
    get_citation_manager,
    get_gemini_client,
    get_rag_orchestrator,
    get_retriever,
)
from .middleware import ThreatLevel, get_input_sanitizer, get_output_sanitizer
from .query_history import format_history_string, sanitize_history_messages
from .query_models import Message, Query, Response
from .query_sanitization import (
    log_blocked_threat,
    log_output_redaction,
    sanitize_metadata,
    sanitize_quiz_payload,
    sanitize_suggested_prompts,
    sanitize_value,
)

HISTORY_CONTEXT_MAX_MESSAGES = 10


async def process_query_core(
    query: Query,
    request: Request,
    *,
    include_reasoning: bool,
    include_metadata: bool,
    include_duration_ms: bool,
    include_chat_history_in_orchestrator: bool,
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

    # NOTE: Filter extraction moved to specific pipelines (Orchestrator vs Legacy)
    # to avoid duplication and precedence issues.

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

    # History scope key is reserved for future authenticated sessions.
    # Currently None as no user auth is present.
    history_scope_key = None

    settings = get_settings()
    signing_secret = settings.SECRET_KEY
    timeout_ms = max(float(getattr(settings, "RAG_TIMEOUT_MS", 0) or 0), 0.0)
    timeout_seconds = timeout_ms / 1000.0
    
    if not signing_secret:
        # Fail open with warning for internal deployments (no auth)
        logger.warning("History signing secret not configured. History integrity checks skipped.")
        history_verified = True  # Trust history since we can't verify
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
                    f"History signature verification FAILED for conversation {query.conversation_id}. "
                    "Discarding untrusted history for safety."
                )
                trusted_history = None
                history_verified = False
        elif not signing_secret:
            # Secret missing, already logged warning above, trust history
            pass
        elif not history_scope_key:
            # Secret exists but no signature provided (anonymous request)
            # In strict mode we might discard, but here we allow it with warning if enabled
            # For now, consistent with previous logic: warn and discard if signature expected but missing
            if query.history_signature is None:
                # It's an unsigned request but we have a secret. 
                # If this is the first message, history might be empty/short.
                # If history is present without signature, discard it.
                logger.warning(
                    "History provided for anonymous request without signature. "
                    "Discarding untrusted history."
                )
                history_verified = False
                trusted_history = None
    elif trusted_history and not query.conversation_id:
        # History present but no conversation_id to verify against - discard for safety
        logger.warning(
            "History provided without conversation_id. "
            "Discarding unassociated history for safety."
        )
        history_verified = False
        trusted_history = None

    history_window = trusted_history[-HISTORY_CONTEXT_MAX_MESSAGES:] if trusted_history else None

    # Sanitize history once for both pipelines
    cleaned_history = sanitize_history_messages(history_window)
    scoped_history = cleaned_history

    input_history_len = len(history_window) if history_window else 0
    history_items_dropped = input_history_len - len(cleaned_history)

    if rag_orchestrator is not None:
        logger.debug("Using multi-agent RAG orchestrator")
        
        # Orchestrator handles filter extraction internally to ensure
        # extracted filters take precedence over rewritten ones correctly.
        orchestrator_kwargs: Dict[str, Any] = {
            "query": safe_query,
            "metadata_filters": None,
        }
        
        if include_chat_history_in_orchestrator and scoped_history:
            orchestrator_history = [{"role": m.role, "content": m.content} for m in scoped_history]
            orchestrator_kwargs["chat_history"] = orchestrator_history

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

        if scoped_history:
            history_context = format_history_string(scoped_history)
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
            kb_citations = citation_manager.extract_citations_from_vector_results(
                vector_results,
                max_citations=5,
            )
            citation_info = citation_manager.format_citations_for_response(
                kb_citations,
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

    sanitized_sources = sanitize_value(
        processed_results.get("sources") or ["knowledge_base"],
        output_sanitizer,
    )
    safe_sources = [str(s) for s in sanitized_sources if s] or ["knowledge_base"]

    sanitized_metadata = None
    history_signals_triggered = history_items_dropped > 0 or (
        history_verified is False and original_history_present
    )

    if include_metadata or history_signals_triggered:
        raw_metadata = processed_results.get("metadata") or {}
        sanitized_metadata = sanitize_metadata(
            raw_metadata,
            output_sanitizer,
            history_verification_failed=original_history_present and not history_verified,
            history_items_dropped=history_items_dropped,
        )

    sanitized_quiz = sanitize_quiz_payload(processed_results.get("quiz"), output_sanitizer)
    sanitized_suggested_prompts = sanitize_suggested_prompts(
        processed_results.get("suggested_prompts"), output_sanitizer
    )

    return Response(
        answer=sanitized_answer,
        confidence=processed_results.get("confidence", 0.0),
        sources=safe_sources,
        conversation_id=conversation_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        citations=processed_results.get("citations"),
        reasoning_steps=sanitized_reasoning_steps,
        metadata=sanitized_metadata,
        quiz=sanitized_quiz,
        suggested_prompts=sanitized_suggested_prompts,
        history_signature=history_signature,
        truncated=processed_results.get("truncated", False),
    )
