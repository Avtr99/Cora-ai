"""Detection helpers for complete and census dataset queries.

Detects when a user query asks for complete enumeration (e.g., "list all CCP
approved programs") or project census aggregation (e.g. "how many VM0047
projects are registered?") rather than a standard semantic search, and produces
the StructuredListSpec needed for Qdrant payload scrolling.
"""

import re
from typing import Any, Dict, Optional, Tuple

from ..registry_config.registry_patterns import (
    RegistryPattern,
    find_document_codes,
    get_merged_registry_patterns,
)
from .structured_spec import StructuredListSpec


def _registry_detection_state() -> tuple[
    list[RegistryPattern], re.Pattern, Dict[str, str], Dict[str, str]
]:
    """Build detection tables from the current merged registry configuration."""
    patterns = get_merged_registry_patterns()
    row_entity_words = {
        word.strip()
        for pattern in patterns
        for word in (pattern.row_entity, pattern.row_entity_plural)
        if word and word.strip()
    }
    display_labels: Dict[str, str] = {}
    registry_lookup: Dict[str, str] = {}
    for pattern in patterns:
        display_labels[pattern.row_entity.lower()] = pattern.row_entity
        display_labels[pattern.row_entity_plural.lower()] = pattern.row_entity
        for marker in pattern.content_markers:
            if marker:
                registry_lookup[marker.lower()] = pattern.name

    row_entity_pattern = re.compile(
        r"\b(?:"
        + "|".join(re.escape(word) for word in sorted(row_entity_words, key=len, reverse=True))
        + r")\b",
        re.IGNORECASE,
    )
    return patterns, row_entity_pattern, display_labels, registry_lookup


# Enumeration only. Standalone "all" / "every" / "what" / "which" / "give"
# / "provide" are common in predicate or lookup questions and must not trigger
# a complete-dataset scroll.
_COLLECTION_WORDS = re.compile(
    r"\b(list(?:\s+all)?|enumerate|show\s+me\s+all|what\s+are\s+all)\b",
    re.IGNORECASE,
)

# Entity-type patterns for metadata-driven inventories (not dataset rows).
# Dataset rows are detected by the row entity pattern built from each
# RegistryPattern's row_entity / row_entity_plural fields.
_ENTITY_PATTERNS: list[Tuple[re.Pattern, str]] = [
    (re.compile(r"\b(?:carbon\s+crediting\s+)?programs?\b", re.IGNORECASE), "program"),
    (re.compile(r"\bmethodolog(?:y|ies)\b", re.IGNORECASE), "methodology"),
    (re.compile(r"\bprojects?\b", re.IGNORECASE), "project"),
    (re.compile(r"\bstandards?\b", re.IGNORECASE), "standard"),
    (re.compile(r"\bregistr(?:y|ies)\b", re.IGNORECASE), "registry"),
]

# Explicit aggregation or enumeration intent over a methodology's project
# rows. Only these phrasings replace vector retrieval: the user is asking for
# a number or an enumeration of the rows themselves, which semantic top-K
# cannot answer because ranking is blind to row attributes.
#
# Deliberately excluded: bare "which", "status", "registered", "issued",
# "credits". Those are ordinary VCM vocabulary — "explain the credit issuance
# process for VM0047 projects" is a methodology question, and replacing its
# retrieval with a project census would answer it from the wrong corpus.
def _build_aggregation_intent(row_entity_pattern: re.Pattern) -> re.Pattern:
    """Build aggregation cues for the current registry row vocabulary."""
    return re.compile(
        r"\b(?:"
        r"how\s+many\b|"
        r"number\s+of\b|"
        r"total\s+number\b|"
        r"count\s+of\b|"
        r"counts?\s+by\b|"
        r"break\s?down\b|"
        r"list(?:\s+all)?\b.*?" + row_entity_pattern.pattern + r"|"
        r"show\s+me\s+all\b.*?" + row_entity_pattern.pattern + r"|"
        r"enumerate\b.*?" + row_entity_pattern.pattern
        + r")",
        re.IGNORECASE,
    )

# Weaker row-level signals. The question probably benefits from exact dataset
# numbers, but it still needs the methodology document and possibly the web,
# so these only *supplement* normal retrieval. No "list all" — that's an
# aggregation cue above.
_ROW_CONTEXT_INTENT = re.compile(
    r"\b(which|status|pipeline|registered|registration|"
    r"under\s+(?:validation|development)|issued|retired|retirements?|credits?|"
    r"prices?|pricing|premiums?|costs?|values?|valuations?|markets?|signals?|"
    r"demand|supply|trends?|trading|spot|forwards?|deals?|transactions?|"
    r"allowances?|compliance|surrendered?|banked?|borrowed?|allocated?|auctioned?|"
    r"verified?|certified?|compliant"
    r")\b",
    re.IGNORECASE,
)

def _extract_registry(
    query_lower: str,
    registry_lookup: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """Return the registry / standard name detected in query_lower, if any.

    Uses the longest matching content-marker from REGISTRY_PATTERNS so
    more-specific markers (e.g. "core carbon principles") beat shorter
    ones (e.g. "ccp").
    """
    if registry_lookup is None:
        _, _, _, registry_lookup = _registry_detection_state()
    best: Optional[Tuple[int, str]] = None
    for marker, name in registry_lookup.items():
        if marker in query_lower:
            marker_len = len(marker)
            if best is None or marker_len > best[0]:
                best = (marker_len, name)
    return best[1] if best else None


def _detect_project_census(
    normalized: str,
    row_entity_pattern: re.Pattern,
    display_labels: Dict[str, str],
    registry_lookup: Dict[str, str],
) -> Optional[StructuredListSpec]:
    """Detect a query that needs exact numbers over dataset rows.

    VCM project rows require a methodology code as the dataset anchor. Other
    carbon-market row entities (allowances, credits, offsets, certificates,
    units, permits) can also be counted if the query names a recognized
    registry and has aggregation/row-level intent. Explicit aggregation intent
    replaces vector retrieval with an exact census; weaker row-level signals
    only supplement it, so the source documents and web fallback stay
    available.
    """
    entity_match = row_entity_pattern.search(normalized)
    if not entity_match:
        return None

    entity = display_labels.get(
        entity_match.group(0).lower(), entity_match.group(0).lower()
    )
    is_project = entity == "project"

    codes = {m.upper() for m in find_document_codes(normalized)}
    if codes and not is_project:
        # VCM methodology codes are anchored to project rows only.
        return None

    if codes:
        code = sorted(codes)[0]
        qdrant_filter: Dict[str, Any] = {"methodology_codes": code, "doc_type": "dataset"}
        display_name = f"registry projects using {code}"
    elif is_project:
        # Project rows need either a methodology code (handled above) or a
        # generic registry/collection request (handled by detect_structured_list_query).
        return None
    else:
        registry = _extract_registry(normalized, registry_lookup)
        if not registry:
            return None
        qdrant_filter = {"doc_type": "dataset", "registry": registry}
        display_name = f"{registry} {entity} records"

    if _build_aggregation_intent(row_entity_pattern).search(normalized):
        mode = "aggregate"
    elif _ROW_CONTEXT_INTENT.search(normalized):
        mode = "supplement"
    else:
        return None

    return StructuredListSpec(
        source="structured_query",
        status="",
        record_type="project",
        display_name=display_name,
        qdrant_filter=qdrant_filter,
        mode=mode,
        record_label=entity_match.group(0).lower(),
    )


def detect_structured_list_query(query: str) -> Optional[StructuredListSpec]:
    """Return a dataset specification when query asks for a complete list.

    Returns None when the query is a semantic / informational question
    that should use standard vector retrieval.

    Detection logic (registry-agnostic):
    0. Project-census fast-path: methodology code + project entity + explicit
       aggregation intent, e.g. "how many VM0047 projects are registered".
       Weaker row-level signals produce a ``supplement`` spec instead.
    1. Normalise the query and check for collection words ("list", "all", ...).
    2. Detect the entity type (program, methodology, project, ...).
    3. Extract the target registry / standard from the query.
    4. Build a Qdrant payload filter appropriate for that registry.

    ICVCM / CCP approved queries use their source dataset's status semantics;
    supported generic VCM queries use the ingestion taxonomy's doc_type or
    category fields. Unsupported entity inventories return None and
    use normal semantic retrieval.
    """
    if not query or not query.strip():
        return None

    normalized = " ".join(query.lower().split())
    patterns, row_entity_pattern, display_labels, registry_lookup = _registry_detection_state()

    project_census = _detect_project_census(
        normalized, row_entity_pattern, display_labels, registry_lookup
    )
    if project_census is not None:
        return project_census

    # Gate 1 — must contain a collection word ...
    is_collection_request = bool(_COLLECTION_WORDS.search(normalized))

    # ... OR reference an "approved" dataset (CCP-specific fast-path).
    is_approved_dataset = bool(re.search(
        r"approved\s+(?:carbon\s+crediting\s+)?(?:programs?|methodolog)",
        normalized,
    ))

    if not is_collection_request and not is_approved_dataset:
        return None

    # Gate 2 — must reference a known entity type
    entity_type: Optional[str] = None
    for pattern, etype in _ENTITY_PATTERNS:
        if pattern.search(normalized):
            entity_type = etype
            break
    if entity_type is None:
        return None

    # Gate 3 — must target a recognised registry / standard
    registry = _extract_registry(normalized, registry_lookup)
    pattern = next((item for item in patterns if item.name == registry), None)
    if pattern is None:
        return None

    plural = {
        "program": "programs",
        "methodology": "methodologies",
        "standard": "standards",
    }.get(entity_type, entity_type + "s")

    # --- Approved-entity status filter ---
    # Some standard bodies (ICVCM CCP, etc.) have a dedicated status value for
    # approved / eligible entities. The pattern now carries this mapping.
    if is_approved_dataset and pattern.approved_status:
        status = pattern.approved_status.get(entity_type)
        if status:
            return StructuredListSpec(
                source=f"{registry} approved dataset",
                status=status,
                record_type=entity_type,
                display_name=f"{registry}-approved {plural}",
                qdrant_filter={"status": status},
            )

    # --- Generic VCM metadata filter ---
    # Only use entity types whose meaning matches ingestion taxonomy. The
    # corpus classifies CSV trackers as dataset rather than project or
    # program, and it has no category=registry entity collection.
    if entity_type not in {"methodology", "standard"}:
        return None

    qdrant_filter: Dict[str, Any] = {}
    if entity_type == "methodology":
        qdrant_filter["doc_type"] = "methodology"
    else:
        qdrant_filter["category"] = "standard"

    # Prefer the standard field for standards bodies, registry field for
    # credit-issuing registries. Both are declared on the pattern.
    if pattern.is_standards_body:
        qdrant_filter["standard"] = registry
    else:
        qdrant_filter["registry"] = registry

    display = f"{registry} {plural}"
    return StructuredListSpec(
        source="structured_query",
        status="",
        record_type=entity_type,
        display_name=display,
        qdrant_filter=qdrant_filter,
    )


def detect_structured_list_query_any(
    *queries: str,
) -> Optional[StructuredListSpec]:
    """Return the first spec from independently checked queries.

    Check the original user text first, then the rewritten query. Do not
    concatenate: a lookup plus a rewritten "Verra methodology ..." string
    would otherwise look like an enumeration.
    """
    seen: set[str] = set()
    for query in queries:
        if not query or query in seen:
            continue
        seen.add(query)
        spec = detect_structured_list_query(query)
        if spec is not None:
            return spec
    return None
