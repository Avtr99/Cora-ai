"""
Filter extraction utility for structured query parsing.

Extracts structured filters from natural language queries without LLM calls.
Enables fast, deterministic filtering on Qdrant payloads.

Optimized for:
- O(1) field lookup via pre-computed normalization map
- Single-pass text processing using re.sub with callback
- Pre-compiled regex patterns at module load

Examples:
    "projects from Developer=Nike" → ("projects from", {"Developer": "Nike"})
    "emissions > 1000 for carbon projects" → ("for carbon projects", {"emissions": {"$gt": 1000}})
"""
import re
import logging
from typing import Dict, Any, Tuple, Optional, Set, Union
from functools import lru_cache

from ..config import get_settings
from ..retrieval.schema_discovery import discover_fields_from_payloads

logger = logging.getLogger(__name__)

# --- CONSTANTS & PRE-COMPILED REGEX ---

MAX_QUERY_LENGTH = 4096

# Regex for normalizing field names (replace non-alphanumeric with _)
_NORMALIZE_REGEX = re.compile(r'[^a-zA-Z0-9_]')
_UNDERSCORE_COLLAPSE_REGEX = re.compile(r'_{2,}')

# Equality pattern: field=value, field:value, field="value", field='value'
# Captures: 1=key, 2=double_quoted, 3=single_quoted, 4=unquoted
_EQUALITY_PATTERN = re.compile(
    r'\b([a-zA-Z0-9_]+)\s*[=:]\s*(?:"([^"]+)"|\'([^\']+)\'|(\S+))',
    re.IGNORECASE
)

# Range pattern: field > 100, field >= 50.5, field < 1000
# Captures: 1=key, 2=operator, 3=number
_RANGE_PATTERN = re.compile(
    r'\b([a-zA-Z0-9_]+)\s*(>=|<=|>|<)\s*(\d+(?:\.\d+)?)',
    re.IGNORECASE
)

_OPERATOR_MAP = {
    '>': '$gt',
    '>=': '$gte',
    '<': '$lt',
    '<=': '$lte'
}


def _normalize_field_name(field_name: str) -> str:
    """
    Normalize field name for Qdrant compatibility using pre-compiled regex.
    
    Matches the normalization in CSVLoader to ensure query fields
    match stored field names.
    
    Args:
        field_name: Original field name from query
        
    Returns:
        Normalized field name (spaces/special chars replaced with underscores)
    """
    normalized = _NORMALIZE_REGEX.sub('_', field_name)
    normalized = _UNDERSCORE_COLLAPSE_REGEX.sub('_', normalized)
    return normalized.strip('_')


def _build_field_lookup_map() -> Dict[str, str]:
    """
    Build O(1) lookup map for allowed fields.

    Maps normalized lowercase field names to their canonical names.
    Includes both static config fields and dynamically discovered fields
    from Qdrant payloads.
    """
    allowed_fields = get_allowed_filter_fields()

    field_map = {}
    for field in allowed_fields:
        norm_key = _normalize_field_name(field).lower()
        field_map[norm_key] = field
    return field_map


@lru_cache(maxsize=1)
def _get_field_lookup_map() -> Dict[str, str]:
    """
    Cached wrapper for _build_field_lookup_map.

    Cache is invalidated via invalidate_field_cache() when collection
    schema changes (e.g., after reingestion).
    """
    return _build_field_lookup_map()


def invalidate_field_cache() -> None:
    """Invalidate cached field lookup map after schema changes."""
    _get_field_lookup_map.cache_clear()
    logger.info("Filter extractor field cache invalidated")


def _get_canonical_field(raw_field: str) -> Optional[str]:
    """
    O(1) lookup to check if a field is allowed and get its canonical name.

    Args:
        raw_field: Field name from query

    Returns:
        Canonical field name if allowed, None otherwise
    """
    field_map = _get_field_lookup_map()
    norm_key = _normalize_field_name(raw_field).lower()
    return field_map.get(norm_key)


def get_allowed_filter_fields(collection_name: Optional[str] = None) -> Set[str]:
    """
    Get the set of allowed filter fields from settings.

    Merges statically configured fields with dynamically discovered fields
    from Qdrant payloads, ensuring the query rewriter only suggests fields
    that actually exist in the collection.

    Args:
        collection_name: If provided, also discover fields from Qdrant payloads.
                         Defaults to QDRANT_COLLECTION_NAME from settings.

    Returns:
        Set of field names that can be used for filtering
    """
    settings = get_settings()
    static_fields = settings.get_validated_allowed_filter_fields()

    # Dynamically discover fields from Qdrant if collection name available
    effective = set(static_fields)
    if collection_name is None:
        collection_name = getattr(settings, "QDRANT_COLLECTION_NAME", None)
    if collection_name:
        # discover_fields_from_payloads swallows its own errors and returns an
        # empty set on failure, so static fields remain the safe fallback.
        discovered = discover_fields_from_payloads(collection_name)
        effective.update(discovered)

    return effective


def extract_filters(query: str) -> Tuple[str, Dict[str, Any]]:
    """
    Extract structured filters from a natural language query.
    
    Uses single-pass extraction with re.sub callback for efficiency.
    
    Parses patterns like:
    - field=value
    - field="value with spaces"
    - field='value'
    - field:value
    
    Only extracts filters for fields in ALLOWED_FILTER_FIELDS.
    
    Args:
        query: User query string
        
    Returns:
        Tuple of (cleaned_query, filters_dict)
        - cleaned_query: Query with filter patterns removed
        - filters_dict: Dictionary of {field: value} for Qdrant filtering
        
    Raises:
        ValueError: If query exceeds MAX_QUERY_LENGTH
        
    Examples:
        >>> extract_filters("projects from Developer=Nike")
        ("projects from", {"Developer": "Nike"})
        
        >>> extract_filters("show me doc_type=policy documents")
        ("show me documents", {"doc_type": "policy"})
    """
    if len(query) > MAX_QUERY_LENGTH:
        raise ValueError(f"Query exceeds maximum length of {MAX_QUERY_LENGTH} characters")
    
    filters: Dict[str, Any] = {}
    
    def _substitution_callback(match: re.Match) -> str:
        """Callback for re.sub: extracts filter and returns replacement text."""
        raw_field = match.group(1)
        canonical_field = _get_canonical_field(raw_field)
        
        if not canonical_field:
            return match.group(0)  # Keep original text for non-allowed fields
        
        # Extract value from one of the capture groups
        raw_value = match.group(2) or match.group(3) or match.group(4)
        filters[canonical_field] = _convert_filter_value(raw_value)
        
        return ""  # Remove matched filter from query
    
    # Single-pass extraction and removal
    cleaned_query = _EQUALITY_PATTERN.sub(_substitution_callback, query)
    
    # Clean up extra whitespace
    cleaned_query = " ".join(cleaned_query.split())
    
    return cleaned_query, filters


def _convert_filter_value(value: str) -> Union[str, int, float, bool]:
    """
    Convert a string filter value to appropriate type.
    
    Args:
        value: String value from query
        
    Returns:
        Converted value (int, float, bool, or str)
    """
    # Try boolean first (before int, since '1'/'0' could be either)
    lower_val = value.lower()
    if lower_val in ('true', 'yes'):
        return True
    if lower_val in ('false', 'no'):
        return False
    
    # Try integer
    try:
        return int(value)
    except ValueError:
        pass
    
    # Try float
    try:
        return float(value)
    except ValueError:
        pass
    
    return value


def extract_range_filters(query: str) -> Tuple[str, Dict[str, Any]]:
    """
    Extract range filters from queries (>, <, >=, <=).
    
    Uses single-pass extraction with re.sub callback for efficiency.
    
    Parses patterns like:
    - field > 100
    - field >= 50
    - field < 1000
    - field <= 50.5
    
    Args:
        query: User query string
        
    Returns:
        Tuple of (cleaned_query, range_filters_dict)
        
    Raises:
        ValueError: If query exceeds MAX_QUERY_LENGTH
        
    Note:
        Range filters require Qdrant Range conditions, not MatchValue.
        The returned dict uses special keys like "$gt", "$lt", "$gte", "$lte".
        
    Examples:
        >>> extract_range_filters("emissions > 1000")
        ("", {"emissions": {"$gt": 1000}})
    """
    if len(query) > MAX_QUERY_LENGTH:
        raise ValueError(f"Query exceeds maximum length of {MAX_QUERY_LENGTH} characters")
    
    range_filters: Dict[str, Any] = {}
    
    def _substitution_callback(match: re.Match) -> str:
        """Callback for re.sub: extracts range filter and returns replacement text."""
        raw_field = match.group(1)
        canonical_field = _get_canonical_field(raw_field)
        
        if not canonical_field:
            return match.group(0)  # Keep original text for non-allowed fields
        
        operator = match.group(2)
        raw_value = match.group(3)
        
        # Convert value to number
        try:
            num_value: Union[int, float] = float(raw_value) if '.' in raw_value else int(raw_value)
        except ValueError:
            return match.group(0)  # Keep original if value conversion fails
        
        qdrant_op = _OPERATOR_MAP.get(operator)
        if not qdrant_op:
            return match.group(0)
        
        # Initialize nested dict if needed
        if canonical_field not in range_filters:
            range_filters[canonical_field] = {}
        range_filters[canonical_field][qdrant_op] = num_value
        
        return ""  # Remove matched filter from query
    
    # Single-pass extraction and removal
    cleaned_query = _RANGE_PATTERN.sub(_substitution_callback, query)
    
    # Clean up extra whitespace
    cleaned_query = " ".join(cleaned_query.split())
    
    return cleaned_query, range_filters


def parse_query_with_filters(query: str) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    """
    Parse a query extracting both equality and range filters.
    
    Args:
        query: User query string
        
    Returns:
        Tuple of (cleaned_query, equality_filters, range_filters)
        
    Raises:
        ValueError: If query exceeds MAX_QUERY_LENGTH
        
    Examples:
        >>> parse_query_with_filters("Developer=Nike emissions > 1000 carbon projects")
        ("carbon projects", {"Developer": "Nike"}, {"emissions": {"$gt": 1000}})
    """
    if len(query) > MAX_QUERY_LENGTH:
        raise ValueError(f"Query exceeds maximum length of {MAX_QUERY_LENGTH} characters")
    
    # Extract equality filters first
    query_after_eq, eq_filters = extract_filters(query)
    
    # Then extract range filters from remaining query
    cleaned_query, range_filters = extract_range_filters(query_after_eq)
    
    return cleaned_query, eq_filters, range_filters


def clear_field_cache() -> None:
    """
    Clear the cached field lookup map.
    
    Call this if allowed filter fields are updated at runtime.
    """
    _get_field_lookup_map.cache_clear()
