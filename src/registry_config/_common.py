"""
Shared definitions for registry pattern modules.

Contains the ``RegistryPattern`` dataclass and reusable version-pattern
constants.  Split out from ``registry_patterns.py`` so that the three
pattern-list modules (``_registries``, ``_governance``, ``_categories``)
can import the dataclass without creating a circular dependency.
"""

from dataclasses import dataclass
from typing import List


# ── Reusable version-pattern constants ──────────────────────────────
# Most registries use one of these two standard version-pattern sets.
# Patterns with custom version extraction (Verra, Gold Standard) define
# their own ``version_patterns`` inline.
VERSION_STANDARD: List[str] = [
    r'[Vv]ersion[:\s]+(\d+\.?\d*)',
]

VERSION_EXTENDED: List[str] = [
    r'[Vv]ersion[:\s]+(\d+\.?\d*)',
    r'\bv\.?(\d+\.?\d*)\b',
]


@dataclass
class RegistryPattern:
    """
    Configuration for a carbon registry's document patterns.

    Attributes:
        name: Registry name (e.g., "Verra", "Gold Standard")
        content_markers: Phrases that identify this registry in content.
            Matched via case-insensitive **substring** test
            (``marker in text.lower()``).  Keep markers specific — short
            acronyms that appear inside common English words (e.g. bare
            ``"ods"``, ``"saf"``, ``"arr"``) risk false positives.
        id_patterns: Regex patterns to extract document IDs.
        version_patterns: Regex patterns to extract version numbers.
        is_registry: True if this is a real credit-issuing registry
            (Verra, Gold Standard, CDM, etc.).  False for governance /
            standard bodies (ICVCM, SBTi, CORSIA) and topic classifiers
            (Market Intelligence, VCM Policy, REDD+ / NBS, etc.).  When
            False, the metadata extractor stores the name under
            ``category`` instead of ``registry`` so the ``registry``
            field is never polluted with non-registry values.
    """
    name: str
    content_markers: List[str]
    id_patterns: List[str]
    version_patterns: List[str]
    is_registry: bool = True
