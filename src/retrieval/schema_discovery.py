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
import time
from typing import Dict, FrozenSet, List, Optional, Set

from qdrant_client import QdrantClient

from ..config import get_settings

logger = logging.getLogger(__name__)

# Cache for discovered fields per collection (stored as frozenset for immutability)
_discovered_fields_cache: Dict[str, FrozenSet[str]] = {}
_cache_lock = threading.Lock()

# Cache for discovered categorical values per collection.
# Maps collection_name → {field_name: frozenset of values found in payloads}.
# Used by QdrantFilterBuilder to reject filter values that don't exist in the
# corpus (e.g. category="standard" when ingestion only stores "SBTi").
_discovered_categorical_values_cache: Dict[str, Dict[str, FrozenSet[str]]] = {}
_categorical_discovery_failure_cache: Dict[str, float] = {}
_categorical_values_lock = threading.Lock()
_CATEGORICAL_DISCOVERY_FAILURE_TTL_SECONDS = 5.0

# Fields whose values form a small, enumerable taxonomy. Filter values for
# these fields are validated against the corpus — unknown values are dropped
# rather than silently producing zero results.
CATEGORICAL_FILTER_FIELDS: FrozenSet[str] = frozenset(
    {"category", "registry", "standard", "policy_framework"}
)


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


def discover_categorical_values_from_payloads(
    collection_name: str,
    sample_size: int = 1000,
) -> Dict[str, Set[str]]:
    """Sample Qdrant payloads to discover values for categorical metadata fields.

    Used by ``QdrantFilterBuilder`` to validate that a filter value (e.g.
    ``category="SBTi"``) actually exists in the corpus before enforcing it.
    This prevents silent zero-result traps when the rewriter emits a
    plausible-but-nonexistent value like ``category="standard"``.

    Args:
        collection_name: Qdrant collection name.
        sample_size: Number of points to sample.

    Returns:
        Dict mapping each categorical field name to the set of values found.
        Fields with no values in the sample map to an empty set. If discovery
        fails entirely, returns an empty dict (caller should skip validation).
    """
    with _categorical_values_lock:
        if collection_name in _discovered_categorical_values_cache:
            return {
                k: set(v) for k, v in _discovered_categorical_values_cache[collection_name].items()
            }

        failed_at = _categorical_discovery_failure_cache.get(collection_name)
        if failed_at is not None:
            if time.monotonic() - failed_at < _CATEGORICAL_DISCOVERY_FAILURE_TTL_SECONDS:
                return {}
            del _categorical_discovery_failure_cache[collection_name]

        client: Optional[QdrantClient] = None
        try:
            client = _get_qdrant_client()
            values: Dict[str, Set[str]] = {f: set() for f in CATEGORICAL_FILTER_FIELDS}
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
                        for field in CATEGORICAL_FILTER_FIELDS:
                            val = metadata.get(field)
                            if isinstance(val, (list, tuple, set, frozenset)):
                                raw_values = val
                            else:
                                raw_values = (val,)
                            for item in raw_values:
                                if item is not None and item != "":
                                    values[field].add(str(item))

                total_scanned += len(points)
                offset = next_offset
                if next_offset is None:
                    break

            frozen = {k: frozenset(v) for k, v in values.items()}
            _discovered_categorical_values_cache[collection_name] = frozen
            _categorical_discovery_failure_cache.pop(collection_name, None)
            logger.info(
                "Discovered categorical values in collection '%s' from %s points: %s",
                collection_name,
                total_scanned,
                {k: len(v) for k, v in frozen.items()},
            )
            return {k: set(v) for k, v in frozen.items()}

        except Exception as exc:
            _categorical_discovery_failure_cache[collection_name] = time.monotonic()
            logger.warning("Failed to discover categorical values: %s", exc)
            return {}
        finally:
            if client is not None:
                client.close()


def remember_categorical_value(collection_name: str, field: str, value: object) -> None:
    """Add a confirmed value to the per-collection categorical cache."""
    if field not in CATEGORICAL_FILTER_FIELDS or value is None or value == "":
        return

    with _categorical_values_lock:
        cached = _discovered_categorical_values_cache.get(collection_name)
        if cached is None:
            return
        values = set(cached.get(field, frozenset()))
        values.add(str(value))
        cached[field] = frozenset(values)


def invalidate_categorical_values_cache(collection_name: str) -> None:
    """Invalidate categorical values cache for a collection (call after reingestion)."""
    with _categorical_values_lock:
        _discovered_categorical_values_cache.pop(collection_name, None)
        _categorical_discovery_failure_cache.pop(collection_name, None)
    logger.info("Invalidated categorical values cache for collection '%s'", collection_name)


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
