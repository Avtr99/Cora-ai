"""Unified detection of non-answer fallback responses.

A single source of truth for the set of strings that indicate the model
returned an explicit "I don't know" fallback instead of a real answer, or
that the pipeline produced an error fallback that should not be cached.

All layers (caching, web supplementation, cache serving) import from this
module to avoid behavioural drift between them.
"""

from typing import List, Optional

# ---------------------------------------------------------------------------
# Canonical user-facing fallback messages.
# Generation sites must import these constants instead of writing literals —
# the text a user sees and the detection prefixes below cannot drift apart.
# ---------------------------------------------------------------------------

# Shown when the retrieved documents do not address the question. This is also
# the sentinel the system prompt instructs the model to emit (prompts.py
# resolves {non_answer} to this), so it must never mention internal machinery
# like "knowledge base" or "reference data".
NO_ANSWER_FOUND = (
    "I couldn't find an answer to that. "
    "Try rephrasing your question or asking something more specific."
)

# Shown when the model returned no extractable text (empty response).
GENERATION_FAILED_ANSWER = (
    "I couldn't generate a response this time. "
    "Please try again. If it keeps happening, try rephrasing your question."
)

# Hybrid route's unverified-state response when web verification fails.
UNVERIFIED_ANSWER = (
    "I could not find a verified answer to your question. "
    "The knowledge base did not contain directly relevant information and "
    "web verification was unavailable. "
    "Try rephrasing your question or asking something more specific."
)

# Web-route failure strings carried in the `answer` field. Provider-agnostic —
# the configured provider name is already in the logs and the `error` detail.
WEB_TIMEOUT_ANSWER = "Web search timed out. Please try again."
WEB_UNAVAILABLE_ANSWER = (
    "Web search is currently unavailable. "
    "Please try again or check the web search provider configuration."
)
WEB_RETRIEVAL_FAILED_ANSWER = (
    "I couldn't retrieve information from web search. "
    "Please try again. If the problem persists, check the web search "
    "provider configuration."
)

_CANONICAL_NON_ANSWERS: tuple[str, ...] = (
    NO_ANSWER_FOUND,
    GENERATION_FAILED_ANSWER,
    UNVERIFIED_ANSWER,
    WEB_TIMEOUT_ANSWER,
    WEB_UNAVAILABLE_ANSWER,
    WEB_RETRIEVAL_FAILED_ANSWER,
)

# Prefixes are derived from canonical messages so copy changes cannot drift
# from detection. Legacy phrasings remain explicit for old cached responses.
NON_ANSWER_PREFIXES: tuple[str, ...] = tuple(
    answer.partition(".")[0] for answer in _CANONICAL_NON_ANSWERS
) + (
    "Information not found, try rephrasing your question again.",
    "I could not generate an answer based on the retrieved documents.",
)

# Precomputed once — is_non_answer() compares against lowercased text.
_NON_ANSWER_PREFIXES_LOWER: tuple[str, ...] = tuple(
    prefix.lower() for prefix in NON_ANSWER_PREFIXES
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
    return any(normalized.startswith(prefix) for prefix in _NON_ANSWER_PREFIXES_LOWER)


def has_error_source_marker(sources: Optional[List[str]]) -> bool:
    return bool(
        sources
        and any(isinstance(source, str) and source in _ERROR_SOURCE_MARKERS for source in sources)
    )


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
    if has_error_source_marker(sources):
        return False
    return True
