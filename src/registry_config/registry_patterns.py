"""
Registry Patterns Configuration
================================

Defines carbon registry patterns used by:
- Router: to know what's in the knowledge base
- Document loaders: to extract metadata during ingestion
- Query rewriter: to expand acronyms
- Structured query detector: to know each registry's row entity

This module is a thin **aggregation layer** — it re-exports
``RegistryPattern`` and ``REGISTRY_PATTERNS`` so that existing imports
(``from ..registry_config.registry_patterns import RegistryPattern,
REGISTRY_PATTERNS``) continue to work without changes.

The actual pattern definitions live in three focused modules:

  ``_registries``   — 27 credit-issuing registries (``is_registry=True``)
  ``_governance``   —  7 governance / standard bodies (``is_registry=False``)
  ``_categories``   — 14 topic classifiers (``is_registry=False``)

This split keeps each file under 400 lines and groups patterns by
semantic role, making it easier to find and update a specific registry
or category without scrolling through 800 lines of config.

Adding a new registry:
  1. Add a ``RegistryPattern`` to ``_registries.py`` (if it issues credits)
     or ``_governance.py`` (if it's a standard/governance body).
  2. Set ``is_registry=True`` for registries, ``False`` for everything else.
  3. Set ``row_entity`` if the default ``project``/``projects`` is wrong.
  4. Run ``pytest tests/test_metadata_extractor.py`` to verify detection.
"""

import json
import logging
import re
from functools import lru_cache
from typing import List, Optional

from ..config import get_settings

# Re-export the dataclass so consumers don't need to know about _common.
from ._common import RegistryPattern

# Import the three pattern lists.
from ._registries import REGISTRY_PATTERNS as _registries
from ._governance import GOVERNANCE_PATTERNS as _governance
from ._categories import CATEGORY_PATTERNS as _categories

logger = logging.getLogger(__name__)

# Aggregate list — registries first (highest priority for tie-breaks),
# then governance bodies, then topic categories.
REGISTRY_PATTERNS: List[RegistryPattern] = _registries + _governance + _categories


def _load_custom_registry_patterns(path: Optional[str]) -> List[RegistryPattern]:
    """Load extra registry patterns from a JSON file.

    The JSON file should contain a list of objects with the same fields as
    ``RegistryPattern``. Only recognized fields are accepted; unknown keys
    are ignored so the dataclass stays forward-compatible.
    """
    if not path:
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            logger.warning("CUSTOM_REGISTRY_PATTERNS file must contain a JSON list")
            return []
        allowed = set(RegistryPattern.__dataclass_fields__)
        patterns = [
            RegistryPattern(**{k: v for k, v in item.items() if k in allowed})
            for item in data
            if isinstance(item, dict)
        ]
        logger.info("Loaded %d custom registry patterns from %s", len(patterns), path)
        return patterns
    except FileNotFoundError:
        logger.warning("CUSTOM_REGISTRY_PATTERNS file not found: %s", path)
        return []
    except Exception as e:
        logger.warning("Failed to load CUSTOM_REGISTRY_PATTERNS: %s", e)
        return []


@lru_cache(maxsize=8)
def _load_merged_registry_patterns(
    custom_path: Optional[str],
) -> tuple[RegistryPattern, ...]:
    """Load the built-in patterns and the custom patterns for one path."""
    custom = _load_custom_registry_patterns(custom_path)
    return tuple(REGISTRY_PATTERNS) + tuple(custom)


def get_merged_registry_patterns() -> List[RegistryPattern]:
    """Return built-in VCM patterns merged with optional custom patterns."""
    try:
        custom_path = get_settings().CUSTOM_REGISTRY_PATTERNS
    except Exception:
        custom_path = None
    return list(_load_merged_registry_patterns(custom_path))


def _document_code_pattern_key() -> tuple[str, ...]:
    return tuple(sorted({
        pattern
        for registry_pattern in get_merged_registry_patterns()
        for pattern in registry_pattern.id_patterns
    }))


@lru_cache(maxsize=8)
def _get_document_code_pattern(patterns: tuple[str, ...]) -> re.Pattern:
    """Compile the document-code pattern for a registry-pattern snapshot."""
    if not patterns:
        return re.compile(r"(?!)", re.IGNORECASE)
    return re.compile(
        "|".join(f"(?:{pattern})" for pattern in patterns),
        re.IGNORECASE,
    )


# Combined document-code pattern derived from every registry's id_patterns.
# This is the single source of truth for "what is a document code" across
# ingestion, retrieval boosting, and structured-query detection.
DOCUMENT_CODE_PATTERN = _get_document_code_pattern(_document_code_pattern_key())


def clear_registry_cache() -> None:
    """Drop cached registry and document-code patterns."""
    global DOCUMENT_CODE_PATTERN
    _load_merged_registry_patterns.cache_clear()
    _get_document_code_pattern.cache_clear()
    DOCUMENT_CODE_PATTERN = _get_document_code_pattern(_document_code_pattern_key())


__all__ = [
    "RegistryPattern",
    "REGISTRY_PATTERNS",
    "get_merged_registry_patterns",
    "clear_registry_cache",
    "DOCUMENT_CODE_PATTERN",
    "find_document_codes",
]


def find_document_codes(text: str) -> List[str]:
    """Return all document-code matches found in ``text``.

    Capturing groups inside each registry's id_pattern are preferred to the
    full match, so trailing punctuation (e.g. the underscore in ``123G_``)
    is stripped automatically. Falls back to the full match if the pattern
    has no capture group.
    """
    if not text:
        return []
    pattern = _get_document_code_pattern(_document_code_pattern_key())
    return [
        next((g for g in match.groups() if g), match.group(0))
        for match in pattern.finditer(text)
    ]
