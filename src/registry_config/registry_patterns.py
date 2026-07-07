"""
Registry Patterns Configuration
================================

Defines carbon registry patterns used by:
- Router: to know what's in the knowledge base
- Document loaders: to extract metadata during ingestion
- Query rewriter: to expand acronyms

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
  3. Run ``pytest tests/test_metadata_extractor.py`` to verify detection.
"""

from typing import List

# Re-export the dataclass so consumers don't need to know about _common.
from ._common import RegistryPattern

# Import the three pattern lists.
from ._registries import REGISTRY_PATTERNS as _registries
from ._governance import GOVERNANCE_PATTERNS as _governance
from ._categories import CATEGORY_PATTERNS as _categories

# Aggregate list — registries first (highest priority for tie-breaks),
# then governance bodies, then topic categories.
REGISTRY_PATTERNS: List[RegistryPattern] = _registries + _governance + _categories

__all__ = ["RegistryPattern", "REGISTRY_PATTERNS"]
