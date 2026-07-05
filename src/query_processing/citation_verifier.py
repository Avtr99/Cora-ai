"""Citation verification post-pass for RAG answers.

After the LLM generates an answer with inline ``[source name]`` citations, this
module verifies that every citation in the answer actually matches a retrieved
source. This closes the gap between "the LLM was told to cite X" and "the LLM
actually cited X" — a common RAG failure mode where the model paraphrases,
hallucinates, or drops citations.

Pipeline:
1. Extract every ``[...]`` token from the answer.
2. Normalize each via ``normalized_source_key`` (lowercase, stripped, deduplicated).
3. Compare against the retrieved sources list (also normalized).
4. If a citation matches a source exactly → keep it.
5. If a citation is a **substring** of a source (or vice versa) → repair it to
   the full source name. This handles abbreviated citations like ``[Verra]``
   matching ``Verra VCS Methodology v4.1``.
6. If a citation is a fuzzy match (Jaccard token overlap ≥ threshold) → repair.
7. If a citation has no match at all → remove it (hallucinated).

The result is a cleaned answer where every citation is grounded in a real
retrieved source, plus a list of unmatched citations for logging/debugging.
"""

from __future__ import annotations

import re
from typing import Dict, Tuple

from loguru import logger

from ..citations.source_name import normalized_source_key

# Match inline citations: [some text]
_CITATION_RE = re.compile(r"\[([^\[\]]{3,200})\]")

# Minimum token overlap ratio for fuzzy matching.
_FUZZY_MATCH_THRESHOLD = 0.4

# Minimum compact-normalized length for a FORWARD containment match
# (extracted citation is a substring of the source name). This avoids false
# positives on very short substrings like "v" or "the".
_CONTAINMENT_MIN_LEN = 4

# Minimum compact-normalized length for a REVERSE containment match
# (source name is a substring of the extracted citation). Forward containment
# is always safe because it expands an abbreviation (e.g. [Verra] →
# "Verra VCS Methodology v4.1"). Reverse containment can degrade a detailed
# citation to a shorter source name, so require a longer minimum to be
# confident the source is a real match, not a coincidental short substring.
# 12 chars ≈ 2 short words (e.g. "verravcs") — long enough to be meaningful.
_REVERSE_CONTAINMENT_MIN_LEN = 12


def _compact_normalize(text: str) -> str:
    """Normalize text by removing spaces, hyphens, underscores, and lowercasing.

    Used for containment checks so 'Verra' matches 'Verra VCS Methodology v4.1'
    and 'VM0007' matches 'VM 0007'.
    """
    return re.sub(r"[\s\-_]", "", text.lower())


def _tokenize(text: str) -> set[str]:
    """Tokenize text into a set of lowercase alphanumeric tokens."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _fuzzy_match(extracted: str, source_key: str) -> float:
    """Return a similarity score between an extracted citation and a source.

    Uses Jaccard token overlap. Returns a float in [0, 1].
    """
    ext_tokens = _tokenize(extracted)
    src_tokens = _tokenize(source_key)
    if not ext_tokens or not src_tokens:
        return 0.0
    intersection = ext_tokens & src_tokens
    union = ext_tokens | src_tokens
    return len(intersection) / len(union)


# Match numeric/formatted citations handled by the frontend.
_NUMERIC_CITATION_RE = re.compile(
    r"\[(cite_(?:kb|web):\s*\d+|source_\d+|\d+)\]",
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


def verify_citations(
    answer: str,
    sources: list[str],
) -> Tuple[str, list[str]]:
    """Verify and repair inline citations in the answer.

    Args:
        answer: The LLM-generated answer text with ``[source name]`` citations.
        sources: The list of retrieved source names (already cleaned by
            ``clean_source_name`` in ``_prepare_context``).

    Returns:
        (cleaned_answer, unmatched_citations):
        - cleaned_answer: the answer with citations repaired or removed.
        - unmatched_citations: citations that were removed (for logging).
    """
    if not answer or not sources:
        return answer, []

    # Build lookups: normalized_key -> display_name, compact_key -> display_name
    source_map: dict[str, str] = {}
    compact_source_map: dict[str, str] = {}
    for src in sources:
        if not src:
            continue
        key = normalized_source_key(src)
        if key:
            source_map[key] = src
            compact_source_map[_compact_normalize(src)] = src

    if not source_map:
        return answer, []

    # Find all citations in the answer.
    citations = list(_CITATION_RE.finditer(answer))
    if not citations:
        return answer, []

    unmatched: list[str] = []
    # Process citations right-to-left so replacements don't shift offsets.
    repairs: list[Tuple[int, int, str]] = []  # (start, end, replacement)

    for match in reversed(citations):
        extracted = match.group(1).strip()

        # Skip numeric/formatted citations handled by the frontend (e.g. [cite_kb: 1], [source_1]).
        if re.match(r'^\d+$', extracted):
            continue
        if re.match(r'^cite_(kb|web):\s*\d+$', extracted, re.IGNORECASE):
            continue
        if re.match(r'^source_\d+$', extracted, re.IGNORECASE):
            continue

        extracted_key = normalized_source_key(extracted)
        extracted_compact = _compact_normalize(extracted)

        # 1. Exact match → keep as-is.
        if extracted_key in source_map:
            continue

        best_source = None
        match_reason = ""

        # 2. Containment match: the extracted citation is a substring of a
        #    source name (or vice versa). Handles abbreviated citations like
        #    [Verra] → Verra VCS Methodology v4.1.
        #    Forward direction (extracted ⊂ source) is always safe — it expands
        #    an abbreviation. Reverse direction (source ⊂ extracted) requires a
        #    longer minimum length to avoid degrading detailed citations when
        #    the source name is very short (e.g. replacing "[Verra VCS
        #    Methodology v4.1]" with just "[Verra]").
        if len(extracted_compact) >= _CONTAINMENT_MIN_LEN:
            for src_compact, src_name in compact_source_map.items():
                if extracted_compact in src_compact:
                    # Forward: abbreviation → full name. Always safe.
                    if best_source is None or len(src_compact) > len(_compact_normalize(best_source)):
                        best_source = src_name
                        match_reason = "containment"
                elif (
                    src_compact in extracted_compact
                    and len(src_compact) >= _REVERSE_CONTAINMENT_MIN_LEN
                ):
                    # Reverse: citation has extra text beyond the source name.
                    # Only repair if the source is long enough to be meaningful.
                    if best_source is None or len(src_compact) > len(_compact_normalize(best_source)):
                        best_source = src_name
                        match_reason = "reverse_containment"

        # 3. Fuzzy match (Jaccard token overlap) → repair.
        if best_source is None:
            best_score = 0.0
            for src_key, src_name in source_map.items():
                score = _fuzzy_match(extracted, src_key)
                if score > best_score:
                    best_score = score
                    best_source = src_name
                    match_reason = f"fuzzy({score:.2f})"
            if best_score < _FUZZY_MATCH_THRESHOLD:
                best_source = None

        if best_source:
            # Repair: replace the extracted citation with the real source name.
            repairs.append((match.start(), match.end(), f"[{best_source}]"))
            logger.debug(
                "citation_repaired: '%s' -> '%s' (%s)",
                extracted[:60],
                best_source[:60],
                match_reason,
            )
        else:
            # No match → remove the citation.
            repairs.append((match.start(), match.end(), ""))
            unmatched.append(extracted)
            logger.debug(
                "citation_removed: '%s' (no match)",
                extracted[:60],
            )

    # Log the first few removed citations at INFO level for observability.
    # DEBUG-level logs already capture each individual removal; the summary here
    # surfaces the most impactful cases without spamming the logs.
    if unmatched:
        sample = unmatched[:3]
        logger.info(
            "citation_verification_removed %d unmatched citation(s); sample: %s",
            len(unmatched),
            sample,
        )

    # Apply repairs.
    result = answer
    for start, end, replacement in repairs:
        result = result[:start] + replacement + result[end:]

    # Clean up double spaces left by removed citations.
    result = re.sub(r"  +", " ", result).strip()
    # Clean up " ." or " ," left by removed citations at end of sentences.
    result = re.sub(r"\s+([.,;!?])", r"\1", result)

    return result, unmatched


# Match the same legacy/numeric forms the web search normalizer handles.
_KB_LEGACY_CITATION_RE = re.compile(r"\[((?:source_\d+|\d+)(?:,\s*(?:source_\d+|\d+))*)\]", re.IGNORECASE)


def normalize_kb_citations(answer: str, sources: list[str]) -> str:
    """Convert legacy [source_N] / [N] citations to [Knowledge Base, cite: N].

    The base-rag prompt asks for ``[cite_kb: N]``, but models sometimes fall back
    to the source identifiers they see in the context (``<source index="N">``) or
    to web-style ``[source_N]``. This pass keeps those citations usable by the
    frontend without breaking existing source-name citations.
    """
    if not answer or not sources:
        return answer

    max_index = len(sources)

    def _replace(match: re.Match) -> str:
        parts = [p.strip() for p in match.group(1).split(",")]
        nums: list[str] = []
        for part in parts:
            # Strip the optional "source_" prefix and validate the range.
            num = part.lower().removeprefix("source_") if part.lower().startswith("source_") else part
            if num.isdigit() and 1 <= int(num) <= max_index:
                nums.append(num)
        return f"[Knowledge Base, cite: {', '.join(nums)}]" if nums else ""

    answer = _KB_LEGACY_CITATION_RE.sub(_replace, answer)
    # Clean up spacing left by removed citations.
    answer = re.sub(r"  +", " ", answer).strip()
    answer = re.sub(r"\s+([.,;!?])", r"\1", answer)
    return answer


# ─── Citation renumbering after filtering ──────────────────────────────

# Matches all citation marker formats the LLM produces:
#   [cite_kb: 1]  [cite_kb: 1, 2]  [Knowledge Base, cite: 1]  [Web, cite: 1, 2]
_CITE_KB_RE = re.compile(
    r"\[(?:cite_kb:\s*([\d,\s]+)|Knowledge\s+Base,\s*cite:\s*([\d,\s]+))\]",
    re.IGNORECASE,
)
_CITE_WEB_RE = re.compile(
    r"\[(?:cite_web:\s*([\d,\s]+)|Web,\s*cite:\s*([\d,\s]+))\]",
    re.IGNORECASE,
)


def _unique_sources_by_type(citations: list, source_type: str) -> list[str]:
    """Return unique source names for *source_type* in first-seen order."""
    seen: set[str] = set()
    names: list[str] = []
    for c in citations:
        if c.source_type != source_type:
            continue
        key = c.source_name.strip().lower()
        if key and key not in seen:
            seen.add(key)
            names.append(c.source_name)
    return names


def _build_renumber_map(
    original: list, filtered: list, source_type: str
) -> dict[int, int]:
    """Map old 1-indexed position → new 1-indexed position for *source_type*."""
    old_names = _unique_sources_by_type(original, source_type)
    new_names = _unique_sources_by_type(filtered, source_type)
    new_index: dict[str, int] = {}
    for i, name in enumerate(new_names, 1):
        new_index[name.strip().lower()] = i

    mapping: dict[int, int] = {}
    for old_pos, name in enumerate(old_names, 1):
        new_pos = new_index.get(name.strip().lower())
        if new_pos is not None:
            mapping[old_pos] = new_pos
    return mapping


def _replace_numbers(match: re.Match, mapping: dict[int, int]) -> str:
    """Rewrite citation numbers in a matched marker using *mapping*.

    Returns an empty string (removing the marker) when no numbers survive
    the mapping so the frontend never sees a dangling reference.
    """
    raw = match.group(1) or match.group(2) or ""
    nums: list[str] = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            old = int(part)
            new = mapping.get(old)
            if new is not None:
                nums.append(str(new))
    if not nums:
        return ""
    # Splice only the captured number group into the full marker text.
    # Using str.replace would corrupt label text that happens to contain
    # the same digits (e.g. "[VCS v4.1, cite: 1]" → "v4.2").
    full = match.group(0)
    group_idx = 1 if match.group(1) is not None else 2
    start = match.start(group_idx) - match.start(0)
    end = match.end(group_idx) - match.start(0)
    return full[:start] + ", ".join(nums) + full[end:]


def renumber_citation_markers(
    answer: str,
    original_citations: list,
    filtered_citations: list,
) -> str:
    """Rewrite inline citation markers so their numbers match the filtered list.

    After ``filter_citations_by_answer`` removes citations that aren't grounded
    in the answer, the remaining citation list is shorter. But the ``[cite_kb: N]``
    markers in the answer still reference the *original* source indices. This
    function renumbers them so ``N`` refers to the position in the filtered list
    (separated by KB/Web), which is what the frontend displays.

    Markers referencing filtered-out sources are removed entirely.
    """
    if not answer:
        return answer

    kb_map = _build_renumber_map(original_citations, filtered_citations, "knowledge_base")
    web_map = _build_renumber_map(original_citations, filtered_citations, "web")

    answer = _CITE_KB_RE.sub(lambda m: _replace_numbers(m, kb_map), answer)
    answer = _CITE_WEB_RE.sub(lambda m: _replace_numbers(m, web_map), answer)

    # Clean up spacing left by removed markers.
    answer = re.sub(r"  +", " ", answer).strip()
    answer = re.sub(r"\s+([.,;!?])", r"\1", answer)
    return answer
