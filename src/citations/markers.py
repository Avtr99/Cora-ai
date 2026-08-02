"""Shared utilities for parsing inline citation markers.

Single source of truth for the ``[cite_kb: N]`` / ``[Knowledge Base, cite: N]``
/ ``[cite_web: N]`` / ``[Web, cite: N]`` marker formats. Both the citation
filter (deciding which sources to retain) and the citation renumberer
(rewriting marker numbers to match the filtered list) import from here so
they agree on what index ``N`` means.
"""

from __future__ import annotations

import re
from typing import Dict, List, Set

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


def extract_cited_indices(answer: str) -> Dict[str, Set[int]]:
    """Return ``{"knowledge_base": {1, 2}, "web": {3}}`` for every explicit
    citation marker found in *answer*.

    ``N`` is the 1-indexed position of the source within the prompt's
    per-source-type source list (KB sources numbered independently from web
    sources). Use :func:`unique_sources_by_type` to map ``N`` back to a
    source name consistent with the renumberer.
    """
    if not answer:
        return {_KB_TYPE: set(), _WEB_TYPE: set()}

    def _collect(pattern: re.Pattern[str]) -> Set[int]:
        indices: Set[int] = set()
        for match in pattern.finditer(answer):
            for group in match.groups():
                if group:
                    indices.update(
                        int(n) for n in re.split(r"[,\s]+", group.strip()) if n
                    )
                    break
        return indices

    return {
        _KB_TYPE: _collect(CITE_KB_RE),
        _WEB_TYPE: _collect(CITE_WEB_RE),
    }


def unique_sources_by_type(citations: list, source_type: str) -> List[str]:
    """Return unique source names for *source_type* in first-seen order.

    Deduplication uses ``strip().lower()`` — the same convention as the
    renumberer — so the N-th entry here is exactly what ``[cite_kb: N]``
    refers to.
    """
    seen: Set[str] = set()
    names: List[str] = []
    for c in citations:
        if c.source_type != source_type:
            continue
        key = c.source_name.strip().lower()
        if key and key not in seen:
            seen.add(key)
            names.append(c.source_name)
    return names
