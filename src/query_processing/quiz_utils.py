"""Utilities for optional embedded quiz generation in model responses."""

import json
import random
import re
from typing import Any, Dict, Optional, Tuple

QUIZ_SEPARATOR = "|||QUIZ_JSON|||"

_COMPLEX_QUERY_MARKERS = (
    "compare",
    "difference",
    "versus",
    " vs ",
    "analyze",
    "analysis",
    "impact",
    "implications",
    "trade-off",
    "tradeoff",
    "step by step",
    "deep dive",
    "break down",
    "takeaways",
    "why",
    "how",
)

_MIN_QUIZ_OPTIONS = 3
_MAX_QUIZ_OPTIONS = 3


def should_generate_quiz(query: str, *, from_controlled_template: bool = False) -> bool:
    """Return True when a query is complex enough to justify a quiz widget.

    Args:
        query: Query string to evaluate.
        from_controlled_template: If True, the query originates from a controlled/template source
            that prefixes user text with the "user query:" marker. The function will strip this
            marker and evaluate the stripped content. Callers must not set this for arbitrary/
            untrusted input because automatic marker-stripping could be abused or lead to
            unexpected processing. Validate or sanitize template inputs before setting to True.
    """
    raw_query = (query or "").strip()
    if from_controlled_template:
        lowered_raw_query = raw_query.lower()
        user_query_marker = "user query:"
        if user_query_marker in lowered_raw_query:
            marker_index = lowered_raw_query.find(user_query_marker)
            raw_query = raw_query[marker_index + len(user_query_marker):].strip()

    normalized_query = raw_query.lower()
    if not normalized_query:
        return False

    word_count = len(re.findall(r"\w+", normalized_query))
    if word_count >= 14:
        return True

    return any(marker in normalized_query for marker in _COMPLEX_QUERY_MARKERS)


def build_quiz_instruction(include_quiz: bool) -> str:
    """Build compact quiz output instructions for prompt injection into generation prompts."""
    if not include_quiz:
        return (
            "Do not include any quiz section or separator in your response. "
            "Return only the answer text."
        )

    return (
        "When adding a quiz, keep the answer concise (target <= 350 words) so output budget remains available. "
        "After the answer, append a newline, then the exact separator "
        f"'{QUIZ_SEPARATOR}', then a newline and one minified JSON object with keys "
        '"question", "options", "correctIndex", and "explanation". '
        "Use exactly 3 options and keep explanation under 240 characters. "
        "IMPORTANT: Frame quiz questions as domain knowledge questions. "
        "Do NOT reference source document titles or filenames in the question text "
        "(e.g., avoid 'According to the Guidance for Cookstove...' or 'Based on the VCS Methodology...'). "
        "Instead, ask about the concept directly (e.g., 'Which methodology is recommended for...')."
    )


def _parse_quiz_payload(raw_quiz: str) -> Optional[Dict[str, Any]]:
    """Parse and validate a quiz payload produced by the model."""
    if not raw_quiz:
        return None

    quiz_text = raw_quiz.strip()
    if not quiz_text:
        return None

    first_brace = quiz_text.find("{")
    last_brace = quiz_text.rfind("}")
    if first_brace == -1 or last_brace == -1 or first_brace >= last_brace:
        return None

    quiz_text = quiz_text[first_brace:last_brace + 1]

    try:
        data = json.loads(quiz_text)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        return None

    question = str(data.get("question", "")).strip()
    explanation = str(data.get("explanation", "")).strip()

    raw_options = data.get("options")
    if not isinstance(raw_options, list):
        return None

    options = [option.strip() for option in raw_options if isinstance(option, str) and option.strip()]
    if len(options) < _MIN_QUIZ_OPTIONS or len(options) > _MAX_QUIZ_OPTIONS:
        return None

    correct_index = data.get("correctIndex")
    if not isinstance(correct_index, int):
        return None
    if correct_index < 0 or correct_index >= len(options):
        return None

    if not question:
        return None

    # Shuffle options and update correctIndex to randomize answer position
    if len(options) > 1:
        # Preserve identity by pairing each option with its original index
        original_correct_index = correct_index
        options_with_index = list(enumerate(options))
        random.shuffle(options_with_index)
        # Rebuild options from shuffled pairs
        options = [option_text for _, option_text in options_with_index]
        # Find new position of the correct option with defensive default
        correct_index = next(
            (i for i, (orig_idx, _) in enumerate(options_with_index) if orig_idx == original_correct_index),
            None
        )
        if correct_index is None:
            # Should not happen if data is valid, but handle gracefully
            return None

    return {
        "question": question,
        "options": options,
        "correctIndex": correct_index,
        "explanation": explanation,
    }


def split_answer_and_quiz(
    raw_text: str,
    enabled: bool = True,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Split answer text and optional quiz JSON from a model response.

    Args:
        raw_text: The model response text.
        enabled: If False, skip splitting and return the raw text as-is.
    """
    normalized_text = (raw_text or "").strip()
    if not enabled or not normalized_text or QUIZ_SEPARATOR not in normalized_text:
        return normalized_text, None

    answer_part, quiz_part = normalized_text.split(QUIZ_SEPARATOR, 1)
    answer_text = answer_part.strip()
    quiz_payload = _parse_quiz_payload(quiz_part)

    if not answer_text:
        answer_text = ""

    return answer_text, quiz_payload
