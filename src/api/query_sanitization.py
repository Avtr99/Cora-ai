"""Sanitization helpers for query request/response processing."""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, List, Optional

from loguru import logger
from pydantic import ValidationError

from ..query_processing.suggested_prompts import MAX_PROMPT_LENGTH
from .middleware import ThreatLevel
from .query_models import QueryMetadataResponse, QuizResponse

MAX_SANITIZE_DEPTH = 20

def _hash_identifier(value: str) -> str:
    """Hash an identifier for pseudonymized logging."""
    return hashlib.sha256(value.encode()).hexdigest()[:16]

def log_blocked_threat(
    threats_detected: list,
    threat_level: ThreatLevel,
    context: str = "query",
) -> str:
    """Log a blocked threat with hashed threat ID for security."""

    threat_hash = hashlib.sha256(
        json.dumps(threats_detected, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]
    logger.warning(
        f"Blocked {context} due to security threat: "
        f"level={threat_level.value} "
        f"threat_id={threat_hash}"
    )
    return threat_hash


def sanitize_value(value: Any, output_sanitizer, depth: int = 0) -> Any:
    """Recursively sanitize a value, handling strings, lists, and dicts."""

    if depth > MAX_SANITIZE_DEPTH:
        return "[nested content truncated]"
    if isinstance(value, str):
        sanitized, _ = output_sanitizer.sanitize(value)
        return sanitized
    if isinstance(value, (int, float, bool, type(None))):
        return value
    if isinstance(value, list):
        return [sanitize_value(item, output_sanitizer, depth + 1) for item in value]
    if isinstance(value, dict):
        return {k: sanitize_value(v, output_sanitizer, depth + 1) for k, v in value.items()}

    sanitized, _ = output_sanitizer.sanitize(str(value))
    return sanitized


def sanitize_suggested_prompts(
    suggested_prompts: Any, output_sanitizer
) -> Optional[List[str]]:
    """Sanitize and validate suggested follow-up prompts before returning to clients."""

    if not isinstance(suggested_prompts, list):
        return None

    sanitized: List[str] = []
    for prompt in suggested_prompts:
        if not isinstance(prompt, str):
            continue
        cleaned = sanitize_value(prompt, output_sanitizer).strip()
        if not cleaned or len(cleaned) > MAX_PROMPT_LENGTH:
            continue
        sanitized.append(cleaned)

    # Require at least 2 valid prompts to be useful
    if len(sanitized) < 2:
        return None

    return sanitized[:3]


def sanitize_quiz_payload(quiz_payload: Any, output_sanitizer) -> Optional[QuizResponse]:
    """Sanitize and validate quiz payload before returning to clients."""

    if not isinstance(quiz_payload, dict):
        return None

    question = sanitize_value(str(quiz_payload.get("question", "")), output_sanitizer).strip()
    raw_options = quiz_payload.get("options")
    correct_index = quiz_payload.get("correctIndex")
    explanation = sanitize_value(str(quiz_payload.get("explanation", "")), output_sanitizer).strip()

    if not question or not isinstance(raw_options, list) or not isinstance(correct_index, int):
        return None

    options = []
    original_option_indices = []
    for original_index, option in enumerate(raw_options):
        sanitized_option = sanitize_value(str(option), output_sanitizer).strip()
        if not sanitized_option:
            continue
        options.append(sanitized_option)
        original_option_indices.append(original_index)

    if len(options) < 2:
        return None

    try:
        new_correct_index = original_option_indices.index(correct_index)
    except ValueError:
        return None

    try:
        return QuizResponse(
            question=question,
            options=options,
            correctIndex=new_correct_index,
            explanation=explanation,
        )
    except ValidationError:
        logger.warning("Quiz payload failed Pydantic validation after sanitization.")
        return None


def log_output_redaction(request, redacted_items: list) -> None:
    """Emit structured audit log entry for redacted output items."""

    if not redacted_items:
        return

    request_id = getattr(request.state, "request_id", "unknown")
    user_id_raw = getattr(request.state, "user_id", "anonymous")
    # Pseudonymize user_id for privacy; keep request_id for correlation
    user_id_hash = _hash_identifier(user_id_raw) if user_id_raw != "anonymous" else "anonymous"

    audit_entry = {
        "event": "output_redaction",
        "request_id": request_id,
        "user_id": user_id_hash,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "redaction_count": len(redacted_items),
        "redaction_hash": hashlib.sha256(json.dumps(redacted_items, sort_keys=True, default=str).encode()).hexdigest()[:16],
    }

    logger.bind(**audit_entry).warning("Sensitive content redacted from AI output")


def sanitize_metadata(
    raw_metadata: Any,
    output_sanitizer,
    *,
    history_verification_failed: bool,
    history_items_dropped: int,
) -> QueryMetadataResponse:
    """Sanitize metadata payload and enforce QueryMetadataResponse schema."""

    sanitized_metadata_dict = sanitize_value(raw_metadata, output_sanitizer) if raw_metadata else {}

    if not isinstance(sanitized_metadata_dict, dict):
        logger.warning("Metadata structure truncated due to excessive nesting")
        sanitized_metadata_dict = {}

    sanitized_metadata_dict["history_verification_failed"] = history_verification_failed
    sanitized_metadata_dict["history_items_dropped"] = history_items_dropped

    try:
        return QueryMetadataResponse(**sanitized_metadata_dict)
    except ValidationError as exc:
        # Log only field locations and error types, not sensitive values
        error_summary = []
        for err in exc.errors():
            loc = ".".join(str(part) for part in err.get("loc", []))
            err_type = err.get("type", "unknown")
            error_summary.append(f"{loc}({err_type})")
        logger.warning(f"Metadata validation failed, using defaults. Fields: {'; '.join(error_summary)}")
        return QueryMetadataResponse(
            history_verification_failed=sanitized_metadata_dict.get(
                "history_verification_failed", False
            ),
            history_items_dropped=sanitized_metadata_dict.get("history_items_dropped", 0),
        )
