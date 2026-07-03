"""Unified detection of non-answer fallback responses.

A single source of truth for the set of strings that indicate the model
returned an explicit "I don't know" fallback instead of a real answer, or
that the pipeline produced an error fallback that should not be cached.

All layers (caching, web supplementation, cache serving) import from this
module to avoid behavioural drift between them.
"""

from typing import List, Optional

# Lowercase, stripped prefixes that mark an answer as a non-answer fallback.
NON_ANSWER_PREFIXES: tuple[str, ...] = (
    "information not found, try rephrasing your question again.",
    "i could not generate an answer based on the retrieved documents.",
)

# Backend markers that indicate a failed/error response.
_ERROR_SOURCE_MARKERS: set[str] = {
    "error_fallback",
    "web_search_failed",
    "web_timeout_fallback",
}


def is_non_answer(answer: str) -> bool:
    """Return True if the answer text is an explicit non-answer fallback.

    Uses prefix matching so variants with trailing whitespace or extra
    text are still detected.  Empty/None answers are also treated as
    non-answers.

    Args:
        answer: Raw answer text from the model or cache.

    Returns:
        True if the answer should be treated as a non-answer.
    """
    normalized = (answer or "").strip().lower()
    if not normalized:
        return True
    return any(normalized.startswith(prefix) for prefix in NON_ANSWER_PREFIXES)


def is_cacheable_answer(answer: str, sources: Optional[List[str]] = None) -> bool:
    """Return True if the answer should be persisted in cache.

    Inverse of :func:`is_non_answer` — excludes empty and fallback answers,
    plus any response whose sources are flagged as an error fallback.

    Args:
        answer: Raw answer text from the model.
        sources: Optional list of source identifiers from the response.

    Returns:
        True if the answer is safe to cache.
    """
    if is_non_answer(answer):
        return False
    if sources and isinstance(sources, list):
        if any(s in _ERROR_SOURCE_MARKERS for s in sources):
            return False
    return True
