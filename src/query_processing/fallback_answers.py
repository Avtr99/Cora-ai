"""Unified detection of non-answer fallback responses.

A single source of truth for the set of strings that indicate the model
returned an explicit "I don't know" fallback instead of a real answer, or
that the pipeline produced an error fallback that should not be cached.

All layers (caching, web supplementation, cache serving) import from this
module to avoid behavioural drift between them.
"""


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

# User-facing refusal for queries outside the assistant's domain. The scope
# gate (web_search.py) and the KB system prompt (prompts.py) share this text
# via scope_refusal_answer() — generation and detection cannot drift apart.
SCOPE_REFUSAL_ANSWER = (
    "I can only help with questions about sustainability, climate, "
    "and carbon markets."
)


def scope_refusal_answer() -> str:
    """Scope refusal matching the active collection's domain.

    When a custom collection is configured (COLLECTION_SYSTEM_INSTRUCTION),
    the refusal names that collection — mirroring _collection_scope_guard in
    prompts.py — otherwise the sustainability default is returned.
    """
    from ..config import get_settings

    settings = get_settings()
    if (settings.COLLECTION_SYSTEM_INSTRUCTION or "").strip():
        name = (settings.COLLECTION_NAME or "").strip()
        if name:
            return f"I can only help with questions about {name}."
        return "I can only help with questions related to this collection."
    return SCOPE_REFUSAL_ANSWER


# Opening shared by every scope-refusal variant ("I can only help with
# questions about ..." / "... related to this collection."). A refusal is a
# terminal answer, not a citation failure — detection lives here, but it must
# NOT join is_non_answer: a refusal must not trigger web supplementation,
# which would answer the off-scope question.
_SCOPE_REFUSAL_PREFIX = "i can only help"


def is_refusal(answer: str) -> bool:
    """Return True if the answer is a scope refusal rather than a citable answer."""
    return (answer or "").strip().lower().startswith(_SCOPE_REFUSAL_PREFIX)


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


def is_error_fallback_result(result) -> bool:
    """True when a result dict carries the typed error-fallback flag."""
    return bool(isinstance(result, dict) and result.get("error_fallback"))


def is_cacheable_answer(answer: str, error_fallback: bool = False) -> bool:
    """Return True if the answer should be persisted in cache.

    Inverse of :func:`is_non_answer` — excludes empty and fallback answers,
    plus any result flagged as an error fallback.

    Args:
        answer: Raw answer text from the model.
        error_fallback: The result dict's typed failure flag (route handlers
            set it on generation/search failures).

    Returns:
        True if the answer is safe to cache.
    """
    if is_non_answer(answer):
        return False
    if error_fallback:
        return False
    return True
