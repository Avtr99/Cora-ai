"""Citation checking, selection, and marker cleanup.

Marker numbers are the prompt's own ``<source index="N">`` / ``source_N``
numbers — the same numbers carried by ``Citation.index``. Checking detects
out-of-range markers; selection maps a marker straight onto the citation with
that index; nothing rewrites the answer's numbering.
"""

from __future__ import annotations

import re
from typing import Callable, Dict, List, Set, Tuple

from .markers import (
    CITE_KB_RE,
    CITE_WEB_RE,
    _KB_TYPE,
    _WEB_TYPE,
    _mask_code,
    iter_cited,
)
from .models import Citation
from ..query_processing.fallback_answers import NO_ANSWER_FOUND, is_non_answer, is_refusal


def marker_type(citation: Citation) -> str:
    """Marker namespace a citation answers to ("knowledge_base" or "web")."""
    if citation.marker_type:
        return citation.marker_type
    return _KB_TYPE if citation.source_type == _KB_TYPE else _WEB_TYPE


def check_citations(answer: str, valid: Dict[str, Set[int]]) -> List[str]:
    """Return the citation errors found in *answer*.

    ``valid`` maps a marker type to the set of indices that exist in the
    prompt. Returns ``[]`` for non-answer fallbacks and scope refusals (both
    carry no markers by design) and a single ``"The answer has no citations."``
    error when a substantive answer has no markers at all.
    """
    if is_non_answer(answer) or is_refusal(answer):
        return []

    invalid: Set[Tuple[str, int]] = set()
    has_markers = False
    for source_type, n in iter_cited(answer):
        has_markers = True
        if n not in valid.get(source_type, set()):
            invalid.add((source_type, n))

    errors = [
        f"[cite_kb: {n}] is not a source in the reference data."
        if source_type == _KB_TYPE
        else f"[Web, cite: {n}] is not a source in the search results."
        for source_type, n in sorted(invalid)
    ]
    if not has_markers:
        errors.append("The answer has no citations.")
    return errors


def select_cited(citations: List[Citation], answer: str) -> List[Citation]:
    """Return the citations the answer cites, in first-cited order.

    A marker ``N`` maps directly onto the citation whose ``index`` is ``N`` in
    the same marker namespace; each citation is included once. Citations
    without an index (e.g. a structured dataset context) are always included.
    """
    indexed: Dict[Tuple[str, int], Citation] = {}
    for citation in citations:
        if citation.index is not None:
            indexed.setdefault((marker_type(citation), citation.index), citation)

    cited: List[Citation] = []
    seen: Set[Tuple[str, int]] = set()
    for source_type, n in iter_cited(answer):
        key = (source_type, n)
        citation = indexed.get(key)
        if citation is not None and key not in seen:
            seen.add(key)
            cited.append(citation)

    cited.extend(c for c in citations if c.index is None)
    return cited


def drop_markers(answer: str, keep: Callable[[str, int], bool]) -> str:
    """Remove citation numbers failing ``keep``; drop markers left empty.

    ``keep`` receives ``(marker_type, n)``. Markers inside fenced code blocks
    and inline code are left untouched.
    """
    if not answer:
        return answer

    masked = _mask_code(answer)
    edits: List[Tuple[int, int, str]] = []
    for pattern, marker_namespace in ((CITE_KB_RE, _KB_TYPE), (CITE_WEB_RE, _WEB_TYPE)):
        for match in pattern.finditer(masked):
            raw = match.group(1) or match.group(2) or ""
            numbers = [part.strip() for part in raw.split(",") if part.strip()]
            kept = [n for n in numbers if n.isdigit() and keep(marker_namespace, int(n))]
            if len(kept) == len(numbers):
                continue
            if not kept:
                edits.append((match.start(), match.end(), ""))
            else:
                # Splice only the captured number group so the label text is
                # preserved verbatim.
                group_idx = 1 if match.group(1) is not None else 2
                edits.append((match.start(group_idx), match.end(group_idx), ", ".join(kept)))

    for start, end, replacement in sorted(edits, key=lambda e: e[0], reverse=True):
        answer = answer[:start] + replacement + answer[end:]

    # Clean up spacing left by removed markers.
    answer = re.sub(r"  +", " ", answer).strip()
    answer = re.sub(r"\s+([.,;!?])", r"\1", answer)
    return answer


CITATION_CORRECTION_TEMPLATE = """<citation_correction>
Your previous answer has citation errors:
{error_lines}

Rewrite the answer. Cite each key claim with [cite_kb: N], where N is the index of a <source index="N"> tag in the reference data.{web_clause} Use only numbers that exist. Keep the content the same where the sources support it. If the sources do not support an answer, reply exactly: "{non_answer}"
</citation_correction>

<previous_answer>
{answer}
</previous_answer>"""


def build_citation_correction(
    prompt: str,
    answer: str,
    errors: List[str],
    *,
    web: bool,
) -> str:
    """Append a citation-correction block to the original generation prompt."""
    web_clause = (
        " Cite web search results with [Web, cite: N], where N is the search result number."
        if web
        else ""
    )
    correction = CITATION_CORRECTION_TEMPLATE.format(
        error_lines="\n".join(f"- {error}" for error in errors),
        web_clause=web_clause,
        non_answer=NO_ANSWER_FOUND,
        answer=answer,
    )
    return f"{prompt}\n\n{correction}"
