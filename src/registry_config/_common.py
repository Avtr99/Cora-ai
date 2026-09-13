"""
Shared definitions for registry pattern modules.

Contains the ``RegistryPattern`` dataclass and reusable version-pattern
constants.  Split out from ``registry_patterns.py`` so that the three
pattern-list modules (``_registries``, ``_governance``, ``_categories``)
can import the dataclass without creating a circular dependency.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


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
        is_standards_body: True if this is a standard/governance body whose
            entity inventories should be filtered by ``metadata.standard``
            rather than ``metadata.registry`` (e.g. ICVCM, SBTi, VCMI,
            GHG Protocol). Defaults to False.
        approved_status: Optional mapping from entity type to the value used
            in ``metadata.status`` for approved / eligible lists. Used by the
            structured-query detector to answer "list all <body> approved
            <entities>" queries. Example: ``{"program": "CCP-Eligible",
            "methodology": "CCP-Approved"}``.
        doc_type: Optional document-type label written into Qdrant chunk
            metadata. Used for typed retrieval (``methodology``, ``standard``,
            ``policy``, ``project``). Defaults to None.
        row_entity: The singular name of a row in this registry's tabular
            dataset (e.g. "project", "allowance", "offset"). Used by the
            structured-query detector to recognize when a user is asking for
            a census over dataset rows. Defaults to "project".
        row_entity_plural: The plural of ``row_entity``. Defaults to appending
            an "s", but can be overridden for irregular plurals.
    """
    name: str
    content_markers: List[str]
    id_patterns: List[str]
    version_patterns: List[str]
    is_registry: bool = True
    is_standards_body: bool = False
    approved_status: Optional[Dict[str, str]] = None
    doc_type: Optional[str] = None
    row_entity: str = "project"
    row_entity_plural: Optional[str] = None

    def __post_init__(self) -> None:
        if self.row_entity_plural is None:
            self.row_entity_plural = self.row_entity + "s"
