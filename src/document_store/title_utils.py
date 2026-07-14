"""Shared utilities for deriving a human-readable document title.

The title is used for:
- the top-level heading in converted markdown,
- the source name in RAG citations.

Design principle: the system must adapt to **any** document type, not just VCM
methodologies and standards. The extraction is therefore layered and
format-agnostic:

1. VCM metadata (registry, publisher, document ID, version) — extracted by
   ``MetadataExtractor`` when registry patterns match. This is domain-specific
   but optional; if no registry is detected, the pipeline falls through.
2. Content-derived title (headings + paragraphs) — format-agnostic heuristics
   that work for any markdown produced by the converter (PDF, CSV, JSON, TXT).
3. Filename fallback — only when content gives nothing useful.

The heuristics avoid hard-coding domain-specific terms (no VCM/ETS/CDR
keyword lists). Instead, the core signal is **heading repetition**: a heading
that appears multiple times in the document is a section label (e.g.
"Monitoring", "Additionality"), not the document title. A heading that appears
only once is likely the title. This is domain-agnostic and self-maintaining.

A small list of ~25 **universal** front-matter words (abstract, introduction,
summary, etc.) is kept because these are genuinely universal across all
document types and are too short to reliably distinguish from real titles by
structure alone.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Universal front-matter / section headings that are not document titles.
#
# This list is intentionally SMALL and domain-agnostic. It contains only words
# that are universal across ALL document types (academic papers, policy docs,
# technical standards, market reports, etc.). Domain-specific terms like
# "additionality", "EU ETS", "biochar" are NOT listed here — they are handled
# by the heading-repetition detection in _extract_content_title, which is
# adaptive and requires no maintenance.
# ---------------------------------------------------------------------------
_UNIVERSAL_GENERIC_WORDS = {
    # Front matter
    "abstract", "acknowledgements", "acknowledgments", "foreword",
    "preface", "introduction", "executive summary", "summary",
    "table of contents", "contents", "version", "draft",
    # Common section headings (universal across all document types)
    "methodology", "methodologies", "standard", "standards",
    "requirements", "definitions", "scope", "monitoring",
    "references", "acronyms", "abbreviations", "glossary",
    "appendix", "annex", "appendices", "annexes",
    # Page / navigation
    "page", "figure", "table", "index",
    # Boilerplate
    "disclaimer", "copyright", "license", "notices",
    "about", "overview", "background",
}

# Filenames that are too generic to be useful display titles.
_GENERIC_FILENAMES = {
    "attachment", "doc", "document", "download", "export", "file",
    "final", "image", "new", "pdf", "report", "scan", "temp", "tmp",
    "untitled", "copy", "version", "draft",
    # Generic document-type stems
    "methodology", "standard", "tool", "toolkit", "guidance", "framework",
}

# Lines that start with these tokens (case-insensitive) are copyright / legal
# notices, not document titles. Used to skip the "first substantial paragraph"
# fallback.
_COPYRIGHT_PREFIXES = (
    "©", "copyright", "all rights reserved", "reproduction",
    "disclaimer", "licensed", "reprinted", "permission",
    "this document", "this publication", "this report",
)

# Regex for parsing markdown headings (# H1, ## H2, ### H3) and bold-as-title.
_HEADING_RE = re.compile(r"^#{1,3}\s+(.+)$")
_BOLD_HEADING_RE = re.compile(r"^\*\*(.+?)\*\*$")

# Regex for reading the first top-level (H1) heading.
_H1_RE = re.compile(r"^#\s+(.+)$")


# Title length limit used for the final display title.
_MAX_TITLE_LEN = 200


def _truncate_title(text: str, max_len: int = _MAX_TITLE_LEN) -> str:
    """Return ``text`` truncated to ``max_len`` with an ellipsis if needed."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _parse_heading(line: str) -> Optional[str]:
    """Extract heading text from a markdown heading or bold-as-title line.

    Returns the heading text without the leading # or ** markers, or None
    if the line is not a heading.
    """
    line = line.strip()
    match = _HEADING_RE.match(line)
    if match:
        return match.group(1).strip()
    bold_match = _BOLD_HEADING_RE.match(line)
    if bold_match:
        return bold_match.group(1).strip()
    return None


def _clean_display_name(name: str) -> str:
    """Turn a raw filename into a readable document title."""
    # Strip path prefixes.
    if "/" in name:
        name = name.rsplit("/", 1)[-1]
    if "\\" in name:
        name = name.rsplit("\\", 1)[-1]
    # Drop common extensions.
    for ext in [".pdf", ".docx", ".doc", ".txt", ".md", ".html"]:
        if name.lower().endswith(ext):
            name = name[: -len(ext)]
            break
    # Underscores and repeated hyphens usually come from sanitized filenames.
    name = name.replace("_", " ").replace("-", " ")
    # Collapse multiple spaces.
    return re.sub(r"\s+", " ", name).strip()


def _is_filename_meaningful(filename: str) -> bool:
    """Return True if the filename looks like a real title, not a placeholder."""
    cleaned = _clean_display_name(filename).lower()
    if len(cleaned) < 8:
        return False
    if cleaned in _GENERIC_FILENAMES:
        return False
    # Reject only if *all* words are generic (e.g., "Final Report PDF").
    # A filename with even one meaningful word (e.g., "Final Report 2024")
    # is better than "document.pdf".
    words = cleaned.split()
    generic_count = sum(1 for word in words if word in _GENERIC_FILENAMES)
    if generic_count >= len(words):
        return False
    return True


def _is_copyright_line(line: str) -> bool:
    """Check if a line is a copyright / legal notice, not a title."""
    lower = line.lower().strip()
    return any(lower.startswith(prefix) for prefix in _COPYRIGHT_PREFIXES)


def _extract_first_heading(markdown: str) -> Optional[str]:
    """Read the first top-level (H1) heading of the markdown."""
    for line in markdown.split("\n")[:20]:
        match = _H1_RE.match(line.strip())
        if match:
            return match.group(1).strip()
    return None


def _is_short_identifier(heading: str) -> bool:
    """Heuristic: is this heading a coded identifier rather than a real title?

    Format-agnostic: a heading is a "short identifier" when it is short (≤40
    chars), contains at least one digit, has ≤3 words, and is not a generic
    word. This catches registry IDs (A6.4-STAN-METH-001, ACM0001, TREES 2.0),
    ISO standards (ISO 14064-2), report numbers, and any other coded reference
    without being tied to a specific domain. The word-count limit prevents
    natural-language titles that happen to contain a year (e.g. "Carbon Market
    Trends 2024") from being misclassified.
    """
    if len(heading) > 40:
        return False
    if heading.lower() in _UNIVERSAL_GENERIC_WORDS:
        return False
    # Must contain at least one digit to look like a coded reference.
    if not re.search(r"\d", heading):
        return False
    # Identifiers are typically ≤3 words; natural-language titles are usually 4+.
    if len(heading.split()) > 3:
        return False
    return True


def _count_heading_occurrences(lines: list[str]) -> Counter[str]:
    """Count how many times each heading appears in the full document.

    A heading that appears multiple times (e.g. "Monitoring" as H2 in several
    chapters) is a section label, not the document title. A heading that
    appears only once is likely the title. This is the core domain-agnostic
    signal that replaces hardcoded keyword lists.
    """
    counts: Counter[str] = Counter()
    in_code_block = False
    for raw_line in lines:
        line = raw_line.strip()
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        heading = _parse_heading(line)
        if heading:
            counts[heading.lower()] += 1
    return counts


def _collect_headings(
    lines: list[str],
    scan_limit: int,
) -> Optional[tuple[list[tuple[int, str]], str]]:
    """Collect heading candidates and the first substantial paragraph.

    Scans the first ``scan_limit`` lines, skipping code blocks, TOC labels,
    version-only lines, numbered sections, and universal front-matter words.
    Returns a list of (line_index, heading_text) and the first substantial
    paragraph after the first heading, if any.
    """
    early_headings: list[tuple[int, str]] = []
    first_substantial_paragraph: Optional[str] = None
    in_code_block = False

    for i, raw_line in enumerate(lines[:scan_limit]):
        line = raw_line.strip()
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        heading = _parse_heading(line)
        if heading:
            lower = heading.lower()
            # Skip version-only lines, TOC labels, and numbered sections.
            if lower.startswith(("version", "table of", "contents", "page")):
                continue
            if re.match(r"^\d+(\.\d+)*\s*\.\s*\w", heading):
                continue
            # Skip universal front-matter words (abstract, introduction, etc.)
            if lower in _UNIVERSAL_GENERIC_WORDS:
                continue
            if len(heading) < 2:
                continue
            early_headings.append((i, heading))
            if len(early_headings) >= 5:
                break
            continue

        # Capture the first substantial paragraph after the first heading.
        # Skip copyright/legal notices, table rows, HTML tags, and generic words.
        if (
            early_headings
            and first_substantial_paragraph is None
            and line
            and len(line) > 20
            and not line.startswith("|")
            and not line.startswith("<")
            and line.lower() not in _UNIVERSAL_GENERIC_WORDS
            and not _is_copyright_line(line)
        ):
            first_substantial_paragraph = line

    return early_headings, first_substantial_paragraph


def _find_doc_id_title(
    early_headings: list[tuple[int, str]],
    doc_id: str,
    heading_counts: Counter[str],
    lines: list[str],
) -> Optional[str]:
    """Find a title using the known document ID.

    Looks for the first early heading that contains the doc_id, then scans the
    next few lines for a subtitle (heading or paragraph). Skips universal
    front-matter words and headings that repeat (section labels).
    """
    normalized_id = re.sub(r"[\s\-_]", "", doc_id.lower())
    for idx, heading in early_headings:
        heading_normalized = re.sub(r"[\s\-_]", "", heading.lower())
        if normalized_id not in heading_normalized:
            continue
        for j in range(idx + 1, min(idx + 6, len(lines))):
            para = lines[j].strip()
            if not para or para.startswith("```"):
                continue
            # If the next line is a heading, use its text as the subtitle.
            # Skip universal generic words and headings that repeat (section labels).
            heading_text = _parse_heading(para)
            if heading_text:
                lower_ht = heading_text.lower()
                if lower_ht in _UNIVERSAL_GENERIC_WORDS:
                    continue
                if heading_counts.get(lower_ht, 0) > 1:
                    continue
                if len(heading_text) > 15:
                    return _truncate_title(f"{heading}: {heading_text}")
                continue
            # Otherwise treat as a paragraph.
            if (
                not para.startswith("|")
                and not para.startswith("<")
                and len(para) > 15
                and para.lower() not in _UNIVERSAL_GENERIC_WORDS
                and not _is_copyright_line(para)
            ):
                return _truncate_title(f"{heading}: {para}")
        return heading
    return None


def _select_best_headings(
    early_headings: list[tuple[int, str]],
    heading_counts: Counter[str],
) -> list[tuple[int, str]]:
    """Return headings that appear only once in the document.

    A heading that repeats (e.g. "Monitoring" in 5 chapters) is a section
    label, not the document title. If every early heading repeats, fall back
    to the full list — the first heading is still the best title candidate.
    """
    unique_headings = [
        (idx, h) for idx, h in early_headings
        if heading_counts.get(h.lower(), 0) <= 1
    ]
    return unique_headings if unique_headings else early_headings


def _combine_identifier(
    first: str,
    candidate_headings: list[tuple[int, str]],
    first_substantial_paragraph: Optional[str],
) -> str:
    """Build a fuller title from a short identifier + subtitle or paragraph."""
    for _, subsequent in candidate_headings[1:]:
        lower = subsequent.lower()
        if subsequent in first or lower in _UNIVERSAL_GENERIC_WORDS:
            continue
        # Skip subsequent headings that are also short identifiers — they
        # are likely references to other documents, not subtitles.
        if _is_short_identifier(subsequent):
            continue
        if re.match(r"^\d+(\.\d+)*\s*\.\s*\w", subsequent):
            continue
        if len(subsequent) >= 5:
            return _truncate_title(f"{first}: {subsequent}")

    if first_substantial_paragraph:
        return _truncate_title(f"{first}: {first_substantial_paragraph}")

    return first


def _extract_content_title(markdown: str, doc_id: Optional[str] = None) -> Optional[str]:
    """Extract a readable title from the document body.

    Uses three domain-agnostic signals:

    1. **Heading repetition**: a heading that appears only once in the full
       document is likely the title; one that appears multiple times is a
       section label (e.g. "Monitoring" in 5 chapters). This replaces
       hardcoded domain keyword lists.
    2. **Universal front-matter filter**: ~25 universal words (abstract,
       introduction, summary, etc.) are always skipped regardless of
       repetition, because they are too short to distinguish from titles.
    3. **Short-identifier combination**: a heading that looks like a coded
       reference (short, has digits, ≤3 words) is combined with the next
       substantive heading or paragraph to form a fuller title.

    If a document ID is known from metadata, it is used to locate the heading
    that likely precedes the full title.

    The scan window is 200 lines to handle cover-page-heavy PDFs where the
    real title appears on page 3-4 after copyright pages and table of contents.
    """
    lines = markdown.splitlines()
    heading_counts = _count_heading_occurrences(lines)
    early_headings, first_substantial_paragraph = _collect_headings(lines, min(200, len(lines)))

    if not early_headings:
        return None

    # If we know the document ID, prefer the heading that contains it.
    if doc_id:
        doc_id_title = _find_doc_id_title(early_headings, doc_id, heading_counts, lines)
        if doc_id_title:
            return doc_id_title

    # Prefer headings that appear only once in the document.
    candidate_headings = _select_best_headings(early_headings, heading_counts)
    first = candidate_headings[0][1]

    # If the first candidate is a short identifier, try to build a fuller title.
    if _is_short_identifier(first):
        return _combine_identifier(first, candidate_headings, first_substantial_paragraph)

    return first if len(first) >= 3 else None


def _build_display_title(
    metadata: dict[str, Any],
    content_title: Optional[str],
    filename: str,
) -> str:
    """Build the best human-readable title from metadata, content, and filename."""
    publisher = metadata.get("publisher")
    doc_id = metadata.get("document_id")
    version = metadata.get("version_number")

    # Only use publisher as the prefix — it is a real organisation name.
    # registry is a topic classifier (e.g. "VCM Policy"), not an org, so it
    # is confusing in a citation.
    prefix = publisher

    title_parts: list[str] = []
    normalized_doc_id = re.sub(r"[\s\-_]", "", doc_id.lower()) if doc_id else ""
    normalized_content_title = re.sub(r"[\s\-_]", "", content_title.lower()) if content_title else ""
    cleaned_filename = _clean_display_name(filename)
    filename_meaningful = _is_filename_meaningful(filename)

    if doc_id and content_title:
        # If the content title already contains the doc ID, don't duplicate it.
        if normalized_doc_id not in normalized_content_title:
            title_parts.append(f"{doc_id}: {content_title}")
        else:
            title_parts.append(content_title)
    elif doc_id and filename_meaningful:
        title_parts.append(f"{doc_id}: {cleaned_filename}")
    elif doc_id:
        title_parts.append(doc_id)
    elif content_title:
        title_parts.append(content_title)
    elif filename_meaningful:
        title_parts.append(cleaned_filename)
    else:
        title_parts.append(cleaned_filename)

    result = " - ".join(part for part in [prefix] + title_parts if part)

    if version and not re.search(rf"\bv{re.escape(version)}\b", result, re.IGNORECASE):
        result += f" v{version}"

    return _truncate_title(result).strip()
