"""
Dynamic schema discovery for Qdrant metadata fields.

Queries Qdrant payloads at runtime to discover which metadata fields
actually exist in the collection, merging them with the static
QDRANT_ALLOWED_FILTER_FIELDS list.

This ensures:
1. The query rewriter only suggests fields that exist in actual payloads
2. Filter extraction accepts fields that are present in Qdrant
3. New fields from CSV/JSON ingestion become usable immediately after reingestion
"""

import logging
import threading
from typing import Dict, FrozenSet, List, Optional, Set

from qdrant_client import QdrantClient

from ..config import get_settings

logger = logging.getLogger(__name__)

# Cache for discovered fields per collection (stored as frozenset for immutability)
_discovered_fields_cache: Dict[str, FrozenSet[str]] = {}
_cache_lock = threading.Lock()


def _get_qdrant_client() -> QdrantClient:
    """Get Qdrant client from application settings."""
    settings = get_settings()
    return QdrantClient(
        url=settings.QDRANT_URL,
        timeout=settings.TIMEOUT,
    )


def discover_fields_from_payloads(
    collection_name: str,
    sample_size: int = 1000,
) -> Set[str]:
    """
    Sample Qdrant payloads to discover which metadata fields actually exist.

    Args:
        collection_name: Qdrant collection name
        sample_size: Number of points to sample for field discovery

    Returns:
        Set of field names present in sampled payloads
    """
    # Hold the lock for the whole discovery so concurrent cold-cache callers
    # don't all run the (expensive) scan. The first caller scans and populates
    # the cache; subsequent callers block briefly, then hit the cached value.
    with _cache_lock:
        if collection_name in _discovered_fields_cache:
            return set(_discovered_fields_cache[collection_name])

        client = _get_qdrant_client()
        try:
            discovered: Set[str] = set()

            # Scroll through points to discover fields
            offset = None
            total_scanned = 0

            while total_scanned < sample_size:
                response = client.scroll(
                    collection_name=collection_name,
                    limit=min(200, sample_size - total_scanned),
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )

                points, next_offset = response
                if not points:
                    break

                for point in points:
                    payload = point.payload or {}
                    metadata = payload.get("metadata", {})
                    if isinstance(metadata, dict):
                        for key in metadata.keys():
                            if metadata[key] is not None and metadata[key] != "":
                                discovered.add(key)

                total_scanned += len(points)
                offset = next_offset
                if next_offset is None:
                    break

            frozen = frozenset(discovered)
            _discovered_fields_cache[collection_name] = frozen
            logger.info(
                "Discovered %s metadata fields in collection '%s' from %s points",
                len(frozen), collection_name, total_scanned
            )
            logger.debug("Discovered fields: %s", sorted(frozen))
            return set(frozen)

        except Exception as exc:
            logger.warning("Failed to discover Qdrant fields: %s", exc)
            return set()
        finally:
            client.close()


def invalidate_field_cache(collection_name: str) -> None:
    """Invalidate cache for a collection (call after reingestion)."""
    with _cache_lock:
        if collection_name in _discovered_fields_cache:
            del _discovered_fields_cache[collection_name]
    logger.info("Invalidated field cache for collection '%s'", collection_name)


def get_effective_filter_fields(
    static_fields: List[str],
    collection_name: Optional[str] = None,
) -> List[str]:
    """
    Return the effective list of filterable fields by merging static config
    with dynamically discovered fields from Qdrant.

    Args:
        static_fields: Base fields from QDRANT_ALLOWED_FILTER_FIELDS
        collection_name: If provided, also discover fields from Qdrant

    Returns:
        Merged list of unique, normalized field names
    """
    effective = set(static_fields)

    if collection_name:
        discovered = discover_fields_from_payloads(collection_name)
        effective.update(discovered)

    return sorted(effective)
