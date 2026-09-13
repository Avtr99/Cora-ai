"""Detection, formatting, and execution models for complete dataset queries.

Provides the unified interface for structured dataset retrieval, re-exporting:
- StructuredListSpec: data specification for metadata-scrolled dataset queries
- detect_structured_list_query: single query detector
- detect_structured_list_query_any: multi-query variant (original + rewritten)
- build_structured_context: compact context builder with deterministic aggregates
"""

from .structured_context import build_structured_context
from .structured_detection import (
    detect_structured_list_query,
    detect_structured_list_query_any,
)
from .structured_spec import StructuredListSpec

__all__ = [
    "StructuredListSpec",
    "build_structured_context",
    "detect_structured_list_query",
    "detect_structured_list_query_any",
]
