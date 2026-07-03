"""
Orchestrator Query Utilities
Utility functions for query processing in the RAG orchestrator:
- Cache key generation
- Query change detection
- Rewrite mode selection
- Date context attachment
"""

import functools
import hashlib
import re
from typing import AbstractSet, Dict, List, Optional, Set, Tuple

from ..registry_config.registry_patterns import REGISTRY_PATTERNS

# Defensive bound for untrusted query scanning with REGISTRY_PATTERNS regexes.
# Limits worst-case CPU even if a pattern regresses into expensive backtracking.
MAX_DOCUMENT_ID_SCAN_CHARS = 4096

# Tokens that unambiguously signal a comparison/contrast intent.
# We use token-based matching (not a broad regex) so substrings like
# "indifferent" do NOT match "different" and standalone words like "other"
# or "between" do NOT trigger false positives.
_COMPARISON_TOKENS = frozenset({
    "compare", "compares", "compared", "comparing", "comparison",
    "versus", "vs", "vs.",
    "differ", "differs", "different", "difference", "differences", "differing",
    "contrast", "contrasts", "contrasted", "contrasting",
})


def _is_comparison_query(query: str) -> bool:
    """Check if the query intends to compare/contrast multiple documents.

    Uses token-based matching to avoid substring false positives
    (e.g. "indifferent" must NOT match "different").
    Weak standalone markers such as "other", "between", "alternatives",
    and "against" are deliberately excluded because they produce false
    positives on narrow factual queries like "What are the other benefits
    of VM0048?", "What happened between 2020 and 2023 for VM0048?", or
    "What are the arguments against VM0048?".
    """
    tokens = set(re.findall(r"[a-zA-Z0-9\.]+", query.lower()))
    return bool(tokens & _COMPARISON_TOKENS)

# Default query types that require full LLM rewrite
DEFAULT_FULL_REWRITE_QUERY_TYPES = frozenset({
    "comparison",
    "multi_part",
    "ambiguous",
    "complex_filter",
})


def _normalize_document_id(candidate: str) -> str:
    """Normalize a document-ID candidate for filter usage."""
    return " ".join(candidate.strip().upper().split())


@functools.lru_cache(maxsize=1)
def _get_registry_id_patterns() -> Tuple[re.Pattern, ...]:
    """Compile and cache registry document-id patterns."""
    compiled: List[re.Pattern] = []
    for registry in REGISTRY_PATTERNS:
        for pattern in registry.id_patterns:
            compiled.append(re.compile(pattern, re.IGNORECASE))
    return tuple(compiled)


def invalidate_registry_id_patterns() -> None:
    """Clear cached compiled registry ID patterns.

    Call this if REGISTRY_PATTERNS is modified at runtime so subsequent
    infer_document_id_from_query() calls pick up updated patterns.
    """
    _get_registry_id_patterns.cache_clear()


def infer_document_id_from_query(query: str) -> Optional[str]:
    """Infer a single document_id from query text using registry-config patterns.

    Uses regexes from REGISTRY_PATTERNS via cached compiled patterns.
    Runtime updates require invalidate_registry_id_patterns() to refresh cache.

    Safety heuristic: only enforce IDs that contain at least one digit to
    avoid false positives on plain category terms.

    Comparison-guard: returns None when the query references multiple distinct
    document IDs OR contains comparison/contrast indicators (e.g. "different
    from", "compare", "versus", "other methodologies"). Enforcing a single
    document_id filter for such queries excludes the very documents needed for
    the comparison and degrades retrieval quality (semantic search plus the
    existing methodology-code boost handle these cases without a hard filter).

    Security note: query scanning is length-bounded to reduce regex DoS risk
    when evaluating untrusted input against multiple patterns.
    """
    if not query or not query.strip():
        return None

    normalized_query = query.strip()
    if len(normalized_query) > MAX_DOCUMENT_ID_SCAN_CHARS:
        normalized_query = normalized_query[:MAX_DOCUMENT_ID_SCAN_CHARS]

    # Collect every distinct registry ID that has at least one digit so we can
    # detect multi-ID queries (e.g. "compare VM0007 and VM0009") and reject the
    # single-filter inference path for them.
    distinct_ids: List[str] = []
    seen: Set[str] = set()
    for pattern in _get_registry_id_patterns():
        for match in pattern.finditer(normalized_query):
            candidate = match.group(1) if match.groups() else match.group(0)
            normalized = _normalize_document_id(candidate)
            if not normalized or not re.search(r"\d", normalized):
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            distinct_ids.append(normalized)
            if len(distinct_ids) > 1:
                # Multiple distinct IDs: caller should retrieve broadly, not
                # constrain to one document.
                return None

    if not distinct_ids:
        return None

    if _is_comparison_query(normalized_query):
        # Single ID but the user is comparing/contrasting against something
        # else (often unnamed, e.g. "other methodologies"). Skip the filter so
        # the retriever can surface peer documents required for the answer.
        return None

    return distinct_ids[0]

# Default markers for time-sensitive queries
DEFAULT_TIME_SENSITIVE_MARKERS = frozenset({
    "latest",
    "recent",
    "current",
    "today",
    "now",
    "this week",
    "this month",
    "this year",
    "new",
    "updated",
    "newest",
})

# Pre-compiled regex patterns for word-boundary matching (prevents substring false positives)
# Example: "by" in "ruby" should NOT match, "new" in "renewable" should NOT match


@functools.lru_cache(maxsize=128)
def _compile_marker_pattern(markers: frozenset) -> re.Pattern:
    """Compile a word-boundary regex pattern for the given markers."""
    # Sort by length descending so multi-word phrases match first
    sorted_markers = sorted(markers, key=len, reverse=True)
    # Escape each marker for regex safety
    escaped = [re.escape(m) for m in sorted_markers]
    # Build alternation pattern with word boundaries
    pattern = r'\b(?:' + '|'.join(escaped) + r')\b'
    return re.compile(pattern, re.IGNORECASE)


def _get_marker_pattern(markers: frozenset) -> re.Pattern:
    """Get cached pattern for markers using LRU cache."""
    return _compile_marker_pattern(markers)


def cache_key(
    prefix: str,
    query: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Generate a cache key from prefix, query, and optional chat history.
    
    Args:
        prefix: Cache namespace prefix (e.g., "rewrite", "route")
        query: The query string
        chat_history: Optional conversation history for context-aware caching
        
    Returns:
        A unique cache key string
    """
    normalized_query = " ".join((query or "").lower().split())
    key_parts = [prefix, normalized_query]
    if chat_history:
        # Include last 3 messages for context-aware caching
        recent = chat_history[-3:]
        history_str = "|".join(
            f"{m.get('role', '')}:{' '.join(m.get('content', '')[:100].lower().split())}"
            for m in recent
        )
        key_parts.append(history_str)
    
    combined = "::".join(key_parts)
    return hashlib.sha256(combined.encode()).hexdigest()[:32]


def query_changed_substantially(original: str, rewritten: str) -> bool:
    """
    Check if the rewritten query differs substantially from the original.
    
    A substantial change is one that would affect routing decisions,
    not just minor formatting or acronym expansions.
    
    Args:
        original: Original query string
        rewritten: Rewritten query string
        
    Returns:
        True if the query changed substantially
    """
    # Normalize for comparison
    orig_normalized = original.lower().strip()
    rewritten_normalized = rewritten.lower().strip()
    
    # Exact match after normalization
    if orig_normalized == rewritten_normalized:
        return False
    
    # Check word-level changes
    orig_words = set(orig_normalized.split())
    rewritten_words = set(rewritten_normalized.split())
    
    # Calculate Jaccard similarity
    intersection = len(orig_words & rewritten_words)
    union = len(orig_words | rewritten_words)
    
    if union == 0:
        return False
    
    similarity = intersection / union
    
    # Substantial change if similarity < 0.7 (30%+ word change)
    return similarity < 0.7


def select_rewrite_mode(
    query: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
    use_quick_rewrite: bool = False,
    full_rewrite_types: AbstractSet[str] = DEFAULT_FULL_REWRITE_QUERY_TYPES,
) -> Tuple[str, str]:
    """
    Select the appropriate rewrite mode based on query characteristics.
    
    Args:
        query: The query string to analyze
        chat_history: Optional conversation history
        use_quick_rewrite: If True, prefer quick local expansion
        full_rewrite_types: Query types that require full LLM rewrite
        
    Returns:
        Tuple of (rewrite_mode, query_type)
        - rewrite_mode: "quick_expand" or "llm"
        - query_type: Detected query type
    """
    query_lower = query.lower()
    
    # Detect query type
    query_type = _detect_query_type(query_lower)
    
    # Determine rewrite mode
    if use_quick_rewrite and query_type not in full_rewrite_types:
        return "quick_expand", query_type
    
    # Use LLM for complex queries or when chat history requires context resolution
    if chat_history and _needs_context_resolution(query_lower, chat_history):
        return "llm", query_type
    
    if query_type in full_rewrite_types:
        return "llm", query_type
    
    # Default to quick expand for simple queries when enabled
    if use_quick_rewrite:
        return "quick_expand", query_type
    
    return "llm", query_type


# Pre-compiled pattern for context markers (pronouns needing resolution)
# Used by _needs_context_resolution to avoid recompiling on each call
_CONTEXT_MARKERS_PATTERN = re.compile(
    r'\b(?:it|this|that|these|those|they|them|the\s+same|above|previous)\b',
    re.IGNORECASE
)

# Pre-compiled pattern for comparison queries
# Covers: compare, versus, difference between, better, vs (with optional period)
_COMPARISON_PATTERN = re.compile(
    r'\b(?:compare|versus|difference\s+between|better|vs\.?)\b',
    re.IGNORECASE
)


def _detect_query_type(query_lower: str) -> str:
    """Detect the type of query for routing decisions.

    Uses word-boundary matching to avoid substring false positives
    (e.g., "by" in "ruby" should NOT trigger comparison).
    """
    # Comparison queries - single pre-compiled pattern check
    if _COMPARISON_PATTERN.search(query_lower):
        return "comparison"

    # Multi-part queries
    if query_lower.count("?") > 1:
        return "multi_part"
    # "and" connecting questions - check for question words after "and"
    if " and " in query_lower and "?" in query_lower:
        # Heuristic: check if "and" connects two question clauses
        parts = query_lower.split(" and ")
        if len(parts) >= 2:
            question_starters = ["what", "how", "why", "when", "where", "who", "which", "can", "is", "are"]
            for part in parts[1:]:
                if any(part.strip().startswith(q) for q in question_starters):
                    return "multi_part"
    
    # Ambiguous pronouns requiring context - word boundary matching
    # Prevents "it" in "item" or "that" in "thatched" from matching
    if re.search(r"\b(it|this|that|these|those|they|them)\b", query_lower):
        return "ambiguous"
    
    # Complex filter queries - tightened to avoid matching common prepositional phrases
    # Uses negative lookahead to exclude common false positives like "in the", "by a", "from my"
    # Only matches when preposition is followed by a likely filter value (not common articles/pronouns)
    # Also excludes reflexive and possessive pronouns to avoid phrases like "believe in yourself" or "differ from mine"
    complex_filter_pattern = r"\b(by|from|in|during|between|after|before)\s+(?!(?:the|a|an|my|our|your|their|this|that|these|those|myself|yourself|himself|herself|itself|ourselves|themselves|mine|yours|his|hers|ours|theirs)\b)\w+"
    if re.search(complex_filter_pattern, query_lower):
        return "complex_filter"
    
    # Simple factual queries
    if query_lower.startswith(("what is", "who is", "when", "where", "how many")):
        return "factual"
    
    return "general"


def _needs_context_resolution(
    query_lower: str,
    chat_history: List[Dict[str, str]],
) -> bool:
    """Check if query needs context resolution from chat history.
    
    Uses word-boundary matching to avoid substring false positives
    (e.g., "it" in "item" or "this" in "thistle" should NOT trigger).
    """
    if not chat_history:
        return False
    
    # Check for pronouns or references that need resolution
    # Word boundary matching prevents "it" matching "item", "theme", "iterative"
    return bool(_CONTEXT_MARKERS_PATTERN.search(query_lower))


def attach_current_date_context(
    rewritten_query: str,
    current_date: str,
    markers: AbstractSet[str] = DEFAULT_TIME_SENSITIVE_MARKERS,
) -> str:
    """
    Attach current date context to time-sensitive queries.
    
    Uses word-boundary matching to prevent substring false positives
    (e.g., "new" in "renewable" or "now" in "knowledge" should NOT trigger).
    
    Args:
        rewritten_query: The rewritten query string
        current_date: Current date in ISO format (YYYY-MM-DD)
        markers: Set of time-sensitive marker words
        
    Returns:
        Query with date context appended if time-sensitive
    """
    query_lower = rewritten_query.lower()
    
    # Check if query contains time-sensitive markers using word-boundary matching
    # This prevents "new" in "renewable" or "now" in "knowledge" from matching
    if isinstance(markers, frozenset) and markers is DEFAULT_TIME_SENSITIVE_MARKERS:
        # Use cached pre-compiled pattern for default markers
        pattern = _get_marker_pattern(markers)
        has_marker = bool(pattern.search(query_lower))
    else:
        # Build pattern on-the-fly for custom markers
        pattern = _compile_marker_pattern(frozenset(markers))
        has_marker = bool(pattern.search(query_lower))
    
    if has_marker:
        # Avoid duplicate date context
        if current_date not in rewritten_query:
            return f"{rewritten_query} as of {current_date}"
    
    return rewritten_query
