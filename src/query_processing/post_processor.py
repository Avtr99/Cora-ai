"""
Post-processing pipeline for LLM-generated answers.

Enforces output rules that the model may not reliably follow:
- Word limit enforcement (truncates at sentence boundaries)
- Preamble stripping (removes source-narrating phrases)

Applied after text extraction and quiz splitting, before caching.
"""

import re
from typing import Tuple

# ---------------------------------------------------------------------------
# Preamble patterns – phrases where the model narrates its sources
# ---------------------------------------------------------------------------
_PREAMBLE_PATTERNS: list[re.Pattern] = [
    re.compile(
        r"^(?:according\s+to\s+(?:the\s+)?(?:knowledge\s+base|web\s+(?:results|search)|"
        r"provided\s+(?:info|information|context|documents?))|"
        r"based\s+on\s+(?:the\s+)?(?:(?:retrieved|provided)\s+(?:documents?|info|information|context)|"
        r"my\s+(?:web\s+)?search|web\s+(?:results|search))|"
        r"(?:the\s+)?(?:knowledge\s+base|web\s+(?:results|search))\s+(?:shows?|indicates?|suggests?|states?|mentions?)|"
        r"from\s+(?:the\s+)?(?:knowledge\s+base|web\s+(?:results|search))|"
        r"(?:the\s+)?(?:web\s+)?search\s+results?\s+(?:show|indicate|suggest|reveal))"
        r"[,:]?\s*",
        re.IGNORECASE,
    ),
]

# ---------------------------------------------------------------------------
# Sentence boundary detection
# ---------------------------------------------------------------------------
# Match sentence endings: punctuation followed by whitespace/newline/end
# We'll filter out numeric list markers during iteration instead of in the regex
_SENTENCE_END = re.compile(
    r"""
    [.!?]           # sentence-ending punctuation
    (?:\s+|\n|$)    # followed by whitespace, newline, or end of string
    """,
    re.VERBOSE,
)


def strip_preambles(text: str) -> str:
    """Remove source-narrating preamble phrases from the start of the text.

    Only strips from the very beginning of the text to avoid mangling
    mid-paragraph content. Runs at most 3 passes to handle stacked preambles.
    """
    if not text:
        return text

    original_text = text
    for _ in range(3):
        before = text
        for pattern in _PREAMBLE_PATTERNS:
            text = pattern.sub("", text, count=1)
        text = text.lstrip()
        if text == before:
            break

    # Re-capitalize first character only if we actually stripped something
    if text != original_text and text and text[0].islower():
        text = text[0].upper() + text[1:]

    return text


def enforce_word_limit(text: str, max_words: int = 650) -> Tuple[str, bool]:
    """Truncate *text* at the nearest sentence boundary before *max_words*.

    Uses a small buffer (``max_words`` defaults to 650 for a 600-word prompt
    rule) so short overruns aren't penalised. If the text is already within
    limit, it is returned untouched.

    The algorithm:
    1. If under limit → return as-is.
    2. Walk sentence boundaries. Keep the last boundary whose cumulative
       word count is ≤ ``max_words``. Skip numeric list markers at line start.
    3. If no sentence boundary exists before the limit, fall back to a
       word-level cut (rare with well-formed prose).

    Returns:
        (text, was_truncated): The (possibly truncated) text and a bool
        indicating whether truncation actually occurred.
    """
    if not text:
        return text, False

    words = text.split()
    if len(words) <= max_words:
        return text, False

    # Find sentence boundaries, filtering out numeric list markers at line start
    boundaries: list[int] = []
    for match in _SENTENCE_END.finditer(text):
        pos = match.end()
        # Check if this is a numeric list marker at line start (e.g., "1.", "2.")
        # Look back from the match start to see if it's at a line boundary
        line_start = text.rfind('\n', 0, match.start())
        if line_start == -1:
            line_start = 0
        else:
            line_start += 1  # Skip the newline
        
        line_fragment = text[line_start:match.start()].strip()
        # If the line fragment is just a number followed by the punctuation, skip it
        if line_fragment.isdigit():
            continue
        
        boundaries.append(pos)

    if boundaries:
        # Walk boundaries and pick the last one within the word budget
        best_pos = 0
        for pos in boundaries:
            fragment = text[:pos]
            if len(fragment.split()) <= max_words:
                best_pos = pos
            else:
                break
        if best_pos > 0:
            return text[:best_pos].rstrip(), True

    # Fallback: hard word-level cut (should be rare)
    return " ".join(words[:max_words]).rstrip(), True


def postprocess_answer(
    text: str,
    *,
    max_words: int = 650,
    strip_preamble: bool = True,
) -> Tuple[str, bool]:
    """Run the full post-processing pipeline on an LLM answer.

    Args:
        text: Raw answer text (after quiz splitting).
        max_words: Word budget. Defaults to 650 (buffer over the 600-word
            prompt rule to avoid cutting answers that are only slightly over).
        strip_preamble: Whether to remove source-narrating preambles.

    Returns:
        (cleaned_text, was_truncated): The post-processed answer and a flag
        indicating whether word-limit truncation was applied.
    """
    if not text:
        return text, False

    if strip_preamble:
        text = strip_preambles(text)

    text, was_truncated = enforce_word_limit(text, max_words=max_words)

    return text.strip(), was_truncated
