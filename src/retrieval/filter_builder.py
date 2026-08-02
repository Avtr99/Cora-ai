"""
Qdrant filter construction, validation, and relaxation.

Handles building Qdrant filters from metadata dicts, validating fields
against the collection's payload schema, and progressively relaxing
filters when initial searches return no results.
"""

import asyncio
import itertools
import json
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Filter, FieldCondition, MatchValue

from .schema_discovery import (
    CATEGORICAL_FILTER_FIELDS,
    discover_categorical_values_from_payloads,
    remember_categorical_value,
)

logger = logging.getLogger(__name__)

# Metadata fields that are commonly unpopulated in Qdrant payloads.
# When filter relaxation is needed, these fields are dropped first.
_LOW_PRODUCTIVITY_FILTER_FIELDS = frozenset({"policy_framework"})


class QdrantFilterBuilder:
    """Builds, validates, and relaxes Qdrant metadata filters.

    Encapsulates all filter-related logic so retrievers can delegate
    filter handling without duplicating schema discovery, validation,
    or relaxation code.
    """

    def __init__(
        self,
        vector_store,
        collection_name: str,
    ):
        """
        Args:
            vector_store: LangChain QdrantVectorStore instance.
            collection_name: Qdrant collection name for schema lookups.
        """
        self._vector_store = vector_store
        self.collection_name = collection_name
        self._indexed_filter_fields: Optional[Set[str]] = None
        self._indexed_filter_fields_lock = asyncio.Lock()

    async def get_indexed_filter_fields(self) -> Optional[Set[str]]:
        """Get metadata fields that have payload indexes in Qdrant."""
        if self._indexed_filter_fields is not None:
            return set(self._indexed_filter_fields)

        async with self._indexed_filter_fields_lock:
            if self._indexed_filter_fields is not None:
                return set(self._indexed_filter_fields)

            if not self._vector_store or not hasattr(self._vector_store, "client"):
                return None

            try:
                def _fetch_indexed_fields() -> Set[str]:
                    collection_info = self._vector_store.client.get_collection(
                        self.collection_name
                    )
                    payload_schema = getattr(collection_info, "payload_schema", {}) or {}
                    fields: Set[str] = set()
                    for field_name in payload_schema.keys():
                        if isinstance(field_name, str) and field_name.startswith("metadata."):
                            fields.add(field_name[len("metadata."):])
                    return fields

                indexed_fields = await asyncio.to_thread(_fetch_indexed_fields)

                self._indexed_filter_fields = indexed_fields
                return set(indexed_fields)
            except Exception as exc:
                logger.warning(
                    "Could not fetch payload schema for metadata filter validation "
                    "(collection=%s): %s",
                    self.collection_name,
                    exc,
                )
                return None

    async def partition_filters_by_index(
        self,
        where: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Split filters into indexed (supported) and non-indexed (unsupported) groups.

        If schema discovery fails, returns all filters as supported so Qdrant
        validates them and the caller handles errors via fail-closed logic.
        """
        indexed_fields = await self.get_indexed_filter_fields()
        if indexed_fields is None:
            return dict(where), {}

        supported: Dict[str, Any] = {}
        unsupported: Dict[str, Any] = {}
        for key, value in where.items():
            if key in indexed_fields:
                supported[key] = value
            else:
                unsupported[key] = value

        return supported, unsupported

    @staticmethod
    def build_filter(where: Dict[str, Any]) -> Filter:
        """Build a Qdrant Filter from a metadata dict."""
        conditions = [
            FieldCondition(key=f"metadata.{key}", match=MatchValue(value=value))
            for key, value in where.items()
        ]
        return Filter(must=conditions)

    async def build_validated_filter(
        self,
        where: Optional[Dict[str, Any]],
        allow_unfiltered_fallback: bool,
    ) -> Tuple[Optional[Filter], Optional[Dict[str, Any]]]:
        """Build a Qdrant filter from metadata, validating against indexed fields.

        Two layers of validation:
        1. **Field validation**: the field must have a payload index in Qdrant.
           Unsupported fields are dropped (or raise, depending on
           ``allow_unfiltered_fallback``).
        2. **Value validation**: for categorical fields (``category``,
           ``registry``, ``standard``, ``policy_framework``), the value must
           exist in the collection's payloads. Unknown values are dropped (or
           raise). This prevents silent zero-result traps when the rewriter
           emits a plausible-but-nonexistent value like ``category="standard"``.

        Args:
            where: Metadata filter dict (e.g., {"doc_type": "methodology"})
            allow_unfiltered_fallback: If True, unsupported/unknown filters are
                silently dropped. If False, raises ValueError.

        Returns:
            Tuple of (qdrant_filter, supported_filters). Both are None when
            ``where`` is empty/None.

        Raises:
            ValueError: When unsupported/unknown filters are present and
                ``allow_unfiltered_fallback`` is False.
        """
        if not where:
            return None, None

        supported_filters, unsupported_filters = await self.partition_filters_by_index(where)
        if unsupported_filters:
            unsupported_keys = sorted(unsupported_filters.keys())
            if allow_unfiltered_fallback:
                logger.warning(
                    "Skipping unsupported metadata filters without payload index "
                    "(collection=%s fields=%s)",
                    self.collection_name,
                    unsupported_keys,
                )
            else:
                raise ValueError(
                    "Unsupported metadata filters without payload index "
                    f"(collection={self.collection_name} fields={unsupported_keys})"
                )

        # Validate categorical values against the corpus. A field can be
        # indexed (passes layer 1) yet carry a value that no document has
        # (e.g. category="standard" when ingestion stores "SBTi"). Enforcing
        # such a filter silently returns zero results, which the relaxation
        # machinery cannot rescue (single-filter case is skipped, and
        # ``category`` is not in the low-productivity relax set).
        supported_filters = await self._validate_categorical_values(
            supported_filters, allow_unfiltered_fallback
        )

        qdrant_filter = self.build_filter(supported_filters) if supported_filters else None
        return qdrant_filter, supported_filters

    async def _validate_categorical_values(
        self,
        supported_filters: Dict[str, Any],
        allow_unfiltered_fallback: bool,
    ) -> Dict[str, Any]:
        """Drop categorical filter values that don't exist in the corpus.

        Two-stage check:
        1. **Fast path (sampled)**: check the value against a cached sample of
           up to 1000 points. If the value is in the sample, it's valid — no
           extra Qdrant call needed.
        2. **Targeted existence check**: if the value is NOT in the sample (could
           be a rare category missed by sampling, or a genuinely invalid value),
           do a single scroll with filter (limit=1) to confirm. This prevents
           false positives where a legitimate but rare category is wrongly dropped
           because the sample didn't include it.

        Returns a new dict with invalid-value filters removed. If discovery
        fails entirely, validation is skipped (fail open — don't block retrieval
        on a transient discovery error).
        """
        categorical_in_query = {
            k: v for k, v in supported_filters.items() if k in CATEGORICAL_FILTER_FIELDS
        }
        if not categorical_in_query:
            return supported_filters

        discovered = await asyncio.to_thread(
            discover_categorical_values_from_payloads, self.collection_name
        )
        if not discovered:
            # Discovery failed or collection empty — fail open.
            return supported_filters

        # Stage 1: check against the sampled values.
        potentially_invalid: Dict[str, Any] = {}
        for key, value in categorical_in_query.items():
            known_values = discovered.get(key, set())
            if not known_values:
                # Field has no values in the sample — can't validate, fail open.
                continue
            if str(value) not in known_values:
                potentially_invalid[key] = value

        if not potentially_invalid:
            return supported_filters

        # Stage 2: targeted existence check for values not in the sample.
        # This catches rare categories that the 1000-point sample missed.
        # Each check is a single scroll with filter on an indexed field (cheap).
        confirmed_invalid: Dict[str, Any] = {}
        for key, value in potentially_invalid.items():
            exists = await self._check_value_exists(key, value)
            if not exists:
                confirmed_invalid[key] = value
            else:
                remember_categorical_value(self.collection_name, key, value)
                logger.debug(
                    "Categorical value %s=%r not in sample but confirmed via "
                    "targeted check (rare category in large collection)",
                    key, value,
                )

        if not confirmed_invalid:
            return supported_filters

        invalid_keys = sorted(confirmed_invalid.keys())
        if allow_unfiltered_fallback:
            logger.warning(
                "Dropping metadata filters with unknown categorical values "
                "(collection=%s fields=%s)",
                self.collection_name,
                {k: confirmed_invalid[k] for k in invalid_keys},
            )
            return {k: v for k, v in supported_filters.items() if k not in confirmed_invalid}

        raise ValueError(
            "Metadata filters with unknown categorical values "
            f"(collection={self.collection_name} fields={invalid_keys})"
        )

    async def _check_value_exists(self, field: str, value: Any) -> bool:
        """Check if any point in the collection has metadata.{field}={value}.

        Uses a single scroll with filter (limit=1) on an indexed field — cheap
        and 100% accurate, unlike the sampling-based discovery which can miss
        rare categories in large collections.
        """
        if not self._vector_store or not hasattr(self._vector_store, "client"):
            return True  # Can't check — fail open (don't drop).

        try:
            qdrant_filter = self.build_filter({field: value})

            def _scroll() -> bool:
                points, _ = self._vector_store.client.scroll(
                    collection_name=self.collection_name,
                    limit=1,
                    scroll_filter=qdrant_filter,
                    with_payload=False,
                    with_vectors=False,
                )
                return len(points) > 0

            return await asyncio.to_thread(_scroll)
        except Exception as exc:
            logger.warning(
                "Targeted existence check failed for %s=%r (collection=%s): %s; "
                "failing open (keeping filter)",
                field, value, self.collection_name, exc,
            )
            return True  # Can't confirm invalidity — fail open.

    async def relax_and_retry(
        self,
        query: str,
        supported_filters: Dict[str, Any],
        candidates_count: int,
        allowed_relax_fields: Optional[Set[str]] = None,
        max_attempts: int = 8,
    ) -> Optional[Tuple[List, List[str]]]:
        """Progressively relax filter conditions when initial search returns 0 results.

        Tries dropping combinations of filters incrementally (1 filter, then 2, etc.),
        prioritising low-productivity fields. By default, every field except
        ``document_id`` is eligible for dropping because metadata filters must not
        become hard recall requirements. Returns the first non-empty result set
        along with the list of relaxed field names, or None if all retries fail.
        """
        if allowed_relax_fields is not None:
            allowed = allowed_relax_fields
        elif "document_id" in supported_filters:
            allowed = set(supported_filters) - {"document_id"}
        else:
            # Metadata filters improve precision but must not make the corpus
            # unreachable when their conjunction produces no candidates.
            allowed = set(supported_filters)

        # Sort filter items: low-productivity fields are dropped first.
        filter_items = sorted(
            supported_filters.items(),
            key=lambda item: 0 if item[0] in _LOW_PRODUCTIVITY_FILTER_FIELDS else 1,
        )

        loop = asyncio.get_running_loop()

        def _search(filter_dict: Dict[str, Any]) -> List:
            qdrant_filter = self.build_filter(filter_dict) if filter_dict else None
            return self._vector_store.similarity_search_with_score(
                query=query, k=candidates_count, filter=qdrant_filter,
            )

        attempts = 0
        attempted_drop_sets: Set[frozenset[int]] = set()
        full_drop_indices = tuple(
            i for i, (key, _) in enumerate(filter_items) if key in allowed
        )
        full_drop_set = frozenset(full_drop_indices)
        # Reserve one attempt for complete relaxation when it is not covered by
        # the bounded combination search.
        partial_max_attempts = max_attempts
        if len(full_drop_indices) >= 3:
            partial_max_attempts = max(0, max_attempts - 1)

        # Progressive relaxation: try dropping 1 filter, then 2, etc. Keep the
        # search bounded, then make one final attempt with every relaxable field
        # removed so a bad conjunction cannot hide relevant documents.
        max_drop_count = min(3, len(filter_items) + 1)
        for drop_count in range(1, max_drop_count):
            if attempts >= partial_max_attempts:
                break
            for combo_indices in itertools.combinations(range(len(filter_items)), drop_count):
                if attempts >= partial_max_attempts:
                    break

                dropped_keys = [filter_items[i][0] for i in combo_indices]
                if any(k not in allowed for k in dropped_keys):
                    continue

                drop_set = frozenset(combo_indices)
                if drop_set in attempted_drop_sets:
                    continue
                attempted_drop_sets.add(drop_set)
                relaxed = {k: v for i, (k, v) in enumerate(filter_items) if i not in drop_set}

                try:
                    docs = await loop.run_in_executor(None, _search, relaxed)
                    attempts += 1
                    if docs:
                        logger.info(
                            "Filter relaxation succeeded: dropped %s from filters, "
                            "got %d results",
                            dropped_keys, len(docs),
                        )
                        return docs, dropped_keys
                except Exception as e:
                    attempts += 1
                    logger.warning(
                        "Relaxed filter search failed for dropped keys %s: %s",
                        dropped_keys, e,
                    )

        # Try the complete relaxation once, including the single-filter case.
        # A None filter is intentional here; document_id remains non-relaxable
        # by default, so this only becomes fully unfiltered when safe.
        if full_drop_set and full_drop_set not in attempted_drop_sets and attempts < max_attempts:
            dropped_keys = [filter_items[i][0] for i in full_drop_indices]
            relaxed = {k: v for i, (k, v) in enumerate(filter_items) if i not in full_drop_set}
            try:
                docs = await loop.run_in_executor(None, _search, relaxed)
                attempts += 1
                if docs:
                    logger.info(
                        "Complete filter relaxation succeeded: dropped %s from filters, "
                        "got %d results",
                        dropped_keys, len(docs),
                    )
                    return docs, dropped_keys
            except Exception as e:
                attempts += 1
                logger.warning(
                    "Complete filter relaxation failed for dropped keys %s: %s",
                    dropped_keys, e,
                )

        if attempts >= max_attempts:
            logger.warning(
                "Filter relaxation reached max_attempts=%d; stopping.",
                max_attempts,
            )
        return None


def handle_filter_search_error(
    filter_err: UnexpectedResponse,
    allow_unfiltered_fallback: bool,
) -> Tuple[bool, str, int]:
    """Inspect a Qdrant UnexpectedResponse and decide on fallback.

    Returns:
        Tuple of (should_fallback, error_message, status_code).
    """
    status_code = filter_err.status_code
    response_body: Dict[str, Any] = {}
    try:
        response_body = filter_err.structured()
    except (ValueError, json.JSONDecodeError):
        response_body = {}

    error_message = (
        response_body.get("status", {}).get("error", "")
        if isinstance(response_body, dict)
        else ""
    )
    index_missing_error = "index required but not found" in error_message.lower()
    should_fallback = (
        status_code == 400
        and index_missing_error
        and allow_unfiltered_fallback
    )
    return should_fallback, error_message, status_code
