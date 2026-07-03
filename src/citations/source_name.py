"""Source-name normalization utilities."""

from __future__ import annotations

from urllib.parse import unquote, urlparse

from .config import (
    _EXTENSION_STRIP_RE,
    _FORMATTING_SEP_RE,
    _KNOWN_SOURCE_ACRONYMS,
    _METHODOLOGY_ID_RE,
    _MULTISPACE_RE,
    _NUMERIC_PREFIX_RE,
    _SOURCE_PREFIX_RE,
    _TITLE_CASE_LOWER,
    _VERSION_PREFIX_RE,
    _VERSION_TOKEN_RE,
)


def clean_source_name(name: str) -> str:
    """Strip path prefixes/extensions and normalize source names for display."""
    if not name:
        return name

    cleaned = name
    for _ in range(2):
        decoded = unquote(cleaned)
        if decoded == cleaned:
            break
        cleaned = decoded

    parsed = urlparse(cleaned)
    if parsed.scheme and parsed.netloc:
        cleaned = parsed.path or parsed.netloc

    cleaned = _SOURCE_PREFIX_RE.sub("", cleaned)
    cleaned = cleaned.replace("\\", "/")
    if "/" in cleaned:
        cleaned = cleaned.split("/")[-1]

    cleaned = _EXTENSION_STRIP_RE.sub("", cleaned)
    version_match = _VERSION_PREFIX_RE.match(cleaned)
    if version_match:
        cleaned = cleaned[version_match.end():]
    cleaned = _NUMERIC_PREFIX_RE.sub("", cleaned)
    cleaned = _FORMATTING_SEP_RE.sub(" ", cleaned)
    cleaned = _MULTISPACE_RE.sub(" ", cleaned).strip()

    if not cleaned:
        return cleaned

    parts = cleaned.split()
    return " ".join(_smart_title_case(parts))


def normalized_source_key(name: str) -> str:
    """Canonical source-name key for dedupe."""
    return clean_source_name(name).strip().lower()


def _smart_title_case(parts: list[str]) -> list[str]:
    result: list[str] = []
    for index, part in enumerate(parts):
        lowered = part.lower()
        if _METHODOLOGY_ID_RE.match(part):
            result.append(part.upper())
        elif _VERSION_TOKEN_RE.match(part):
            result.append(part)
        elif lowered in _KNOWN_SOURCE_ACRONYMS:
            result.append(lowered.upper())
        elif part.isupper() and len(part) >= 2:
            result.append(part)
        elif index > 0 and lowered in _TITLE_CASE_LOWER:
            result.append(lowered)
        else:
            result.append(part.title())
    return result
