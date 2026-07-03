"""Utilities for generating suggested follow-up prompts in model responses."""

import json
from typing import List, Optional, Tuple

SUGGESTED_PROMPTS_SEPARATOR = "|||SUGGESTED_PROMPTS_JSON|||"

_MIN_PROMPTS = 2
_MAX_PROMPTS = 3
MAX_PROMPT_LENGTH = 150


def should_generate_suggested_prompts(query: str) -> bool:
    """Return True when a query warrants suggested follow-up prompts.

    The orchestrator already routes greetings and conversational queries
    away from the answer-generation pipeline, so we only need to guard
    against empty/None input here.
    """
    normalized = (query or "").strip()
    return bool(normalized)


def build_suggested_prompts_instruction(include_prompts: bool) -> str:
    """Build compact suggested-prompts output instructions for prompt injection.

    When enabled, the model is instructed to append a separator and a JSON
    array of 2-3 follow-up question strings after the answer (and after any
    quiz payload).
    """
    if not include_prompts:
        return (
            "Do not include any suggested prompts section or separator in your response. "
            "Return only the answer text."
        )

    return (
        "After your answer (and any quiz section if present), append a newline, then the exact "
        f"separator '{SUGGESTED_PROMPTS_SEPARATOR}', then a newline and one minified JSON array "
        "of 2-3 short follow-up questions the user might ask next. Each question must be a plain "
        "string (not an object), concise, phrased as a natural user query. "
        "Questions should explore related concepts, deeper details, or practical implications "
        "of the topic. Do NOT repeat the original question. Do NOT reference source document "
        "titles or filenames. Example: "
        '["How does additionality differ across registries?", "What are the main challenges '
        'in proving additionality?"]'
    )


def _parse_suggested_prompts_payload(raw: str) -> Optional[List[str]]:
    """Parse and validate a suggested-prompts JSON array from model output."""
    if not raw:
        return None

    text = raw.strip()
    if not text:
        return None

    first_bracket = text.find("[")
    last_bracket = text.rfind("]")
    if first_bracket == -1 or last_bracket == -1 or first_bracket >= last_bracket:
        return None

    text = text[first_bracket:last_bracket + 1]

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, list):
        return None

    prompts: List[str] = []
    for item in data:
        if not isinstance(item, str):
            continue
        cleaned = item.strip()
        if not cleaned or len(cleaned) > MAX_PROMPT_LENGTH:
            continue
        prompts.append(cleaned)

    if len(prompts) < _MIN_PROMPTS:
        return None

    return prompts[:_MAX_PROMPTS]


def split_answer_and_suggested_prompts(
    raw_text: str,
    enabled: bool = True,
) -> Tuple[str, Optional[List[str]]]:
    """Split answer text and optional suggested-prompts JSON from a model response.

    The suggested-prompts section appears AFTER any quiz section, delimited by
    the SUGGESTED_PROMPTS_SEPARATOR.

    Args:
        raw_text: The model response text.
        enabled: If False, skip splitting and return the raw text as-is.
    """
    normalized_text = (raw_text or "").strip()
    if not enabled or not normalized_text or SUGGESTED_PROMPTS_SEPARATOR not in normalized_text:
        return normalized_text, None

    answer_part, prompts_part = normalized_text.split(SUGGESTED_PROMPTS_SEPARATOR, 1)
    answer_text = answer_part.strip()
    prompts = _parse_suggested_prompts_payload(prompts_part)

    if not answer_text:
        answer_text = ""

    return answer_text, prompts
