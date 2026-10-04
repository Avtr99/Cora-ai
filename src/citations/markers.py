"""Shared utilities for parsing inline citation markers.

Single source of truth for the ``[cite_kb: N]`` / ``[Knowledge Base, cite: N]``
/ ``[cite_web: N]`` / ``[Web, cite: N]`` marker formats. ``N`` is the chunk's
position in the prompt (``<source index="N">`` for KB chunks, ``source_N`` for
web results) — the same number the displayed citation list uses. There is no
renumbering step anywhere in the pipeline.
"""

from __future__ import annotations

import re
from typing import Dict, Iterator, List, Set, Tuple

# Matches all citation marker formats the LLM produces:
#   [cite_kb: 1]  [cite_kb: 1, 2]  [Knowledge Base, cite: 1]  [Web, cite: 1, 2]
CITE_KB_RE = re.compile(
    r"\[(?:cite_kb:\s*([\d,\s]+)|Knowledge\s+Base,\s*cite:\s*([\d,\s]+))\]",
    re.IGNORECASE,
)
CITE_WEB_RE = re.compile(
    r"\[(?:cite_web:\s*([\d,\s]+)|Web,\s*cite:\s*([\d,\s]+))\]",
    re.IGNORECASE,
)

_KB_TYPE = "knowledge_base"
_WEB_TYPE = "web"

# Code regions where bracketed text is literal content, not a citation marker.
_FENCED_CODE_RE = re.compile(r"```[\s\S]*?```|```[\s\S]*$")
_INLINE_CODE_RE = re.compile(r"`[^`]*`")


def _mask_code(text: str) -> str:
    """Return *text* with fenced code blocks and inline code blanked to spaces.

    Length-preserving, so match offsets stay aligned with the original text.
    """
    masked = _FENCED_CODE_RE.sub(lambda m: " " * len(m.group(0)), text)
    return _INLINE_CODE_RE.sub(lambda m: " " * len(m.group(0)), masked)


def iter_cited(answer: str) -> Iterator[Tuple[str, int]]:
    """Yield ``(source_type, n)`` for every citation marker, in textual order.

    Markers inside fenced code blocks and inline code are ignored. A
    multi-number marker yields one tuple per number, in order.
    """
    if not answer:
        return
    masked = _mask_code(answer)
    matches: List[Tuple[int, str, re.Match]] = []
    for match in CITE_KB_RE.finditer(masked):
        matches.append((match.start(), _KB_TYPE, match))
    for match in CITE_WEB_RE.finditer(masked):
        matches.append((match.start(), _WEB_TYPE, match))
    matches.sort(key=lambda item: item[0])
    for _, source_type, match in matches:
        raw = match.group(1) or match.group(2) or ""
        for part in raw.split(","):
            part = part.strip()
            if part.isdigit():
                yield source_type, int(part)


def extract_cited_indices(answer: str) -> Dict[str, Set[int]]:
    """Return ``{"knowledge_base": {1, 2}, "web": {3}}`` for every explicit
    citation marker found in *answer*.

    ``N`` is the 1-indexed position of the chunk within the prompt's
    per-source-type source list (KB chunks numbered independently from web
    results).
    """
    indices: Dict[str, Set[int]] = {_KB_TYPE: set(), _WEB_TYPE: set()}
    for source_type, n in iter_cited(answer):
        indices[source_type].add(n)
    return indices


# Match numeric/formatted citations handled by the frontend.
_NUMERIC_CITATION_RE = re.compile(
    r"\[(cite_(?:kb|web):\s*\d+|source_\d+)\]",
    re.IGNORECASE,
)

# Default character window within which duplicate numeric citations are collapsed.
_DEFAULT_DEDUPE_WINDOW = 200


def deduplicate_inline_citations(
    answer: str,
    window: int = _DEFAULT_DEDUPE_WINDOW,
) -> str:
    """Collapse duplicate numeric citations that appear close together.

    The LLM often repeats the same citation on every sentence when a single
    source supports a whole paragraph. This post-pass keeps the first
    occurrence within ``window`` characters and removes subsequent duplicates,
    so the answer reads naturally without losing source attribution.
    """
    if not answer or window <= 0:
        return answer

    last_seen: Dict[str, int] = {}
    parts: list[str] = []
    last_end = 0

    for match in _NUMERIC_CITATION_RE.finditer(answer):
        start, end = match.span()
        parts.append(answer[last_end:start])

        key = match.group(1).lower().replace(" ", "")
        if key in last_seen and (start - last_seen[key]) < window:
            # Duplicate within the window: drop it, including the preceding
            # space so the sentence remains clean (e.g. "2023 ." -> "2023.").
            if start > 0 and answer[start - 1] == " ":
                parts.pop()
                parts.append(answer[last_end : start - 1])
        else:
            parts.append(match.group(0))
            last_seen[key] = end

        last_end = end

    parts.append(answer[last_end:])
    return "".join(parts)
