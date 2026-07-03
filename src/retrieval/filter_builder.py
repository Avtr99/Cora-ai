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

        Args:
            where: Metadata filter dict (e.g., {"doc_type": "methodology"})
            allow_unfiltered_fallback: If True, unsupported filters are silently
                dropped. If False, raises ValueError on unsupported filters.

        Returns:
            Tuple of (qdrant_filter, supported_filters). Both are None when
            ``where`` is empty/None.

        Raises:
            ValueError: When unsupported filters are present and
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

        qdrant_filter = self.build_filter(supported_filters) if supported_filters else None
        return qdrant_filter, supported_filters

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
        prioritising low-productivity fields. Only fields listed in
        *allowed_relax_fields* are eligible for dropping. Returns the first non-empty
        result set along with the list of relaxed field names, or None if all retries fail.
        """
        allowed = allowed_relax_fields or _LOW_PRODUCTIVITY_FILTER_FIELDS

        # Sort filter items: low-productivity fields are dropped first.
        filter_items = sorted(
            supported_filters.items(),
            key=lambda item: 0 if item[0] in _LOW_PRODUCTIVITY_FILTER_FIELDS else 1,
        )

        loop = asyncio.get_running_loop()

        def _search(filter_dict: Dict[str, Any]) -> List:
            qdrant_filter = self.build_filter(filter_dict)
            return self._vector_store.similarity_search_with_score(
                query=query, k=candidates_count, filter=qdrant_filter,
            )

        attempts = 0

        # Progressive relaxation: try dropping 1 filter, then 2, etc.
        # max_drop_count is the exclusive upper bound of the range, so with
        # min(3, ...) the effective drop counts are {1, 2}. Dropping more than
        # 2 filters defeats the purpose of metadata filtering and creates
        # unnecessary combinatorial work.
        max_drop_count = min(3, len(filter_items) + 1)
        for drop_count in range(1, max_drop_count):
            if attempts >= max_attempts:
                break
            for combo_indices in itertools.combinations(range(len(filter_items)), drop_count):
                if attempts >= max_attempts:
                    logger.warning(
                        "Filter relaxation reached max_attempts=%d; stopping.",
                        max_attempts,
                    )
                    return None

                dropped_keys = [filter_items[i][0] for i in combo_indices]
                if any(k not in allowed for k in dropped_keys):
                    continue

                relaxed = {k: v for i, (k, v) in enumerate(filter_items) if i not in combo_indices}
                if not relaxed:
                    continue

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

            if attempts >= max_attempts:
                break

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
