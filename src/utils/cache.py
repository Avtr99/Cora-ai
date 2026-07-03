"""
Unified caching module for the RAG system.

Single-tier design: all query result caching is backed by SQLite
(see src/db/sqlite_cache.py and the backend_cache table). This replaces
the previous two-tier (in-memory L1 + SQLite L2) approach — for a
self-hosted local app, SQLite is fast enough and we don't need the
complexity of a separate in-memory layer.

Embedding persistence also lives in SQLite (see embedding_cache table
in migrations/001_initial.sql).
"""
import hashlib
import json
import logging
from typing import Any, Dict, Optional

from ..config import get_settings

logger = logging.getLogger(__name__)


def generate_cache_key(prefix: str, text: str) -> str:
    """Generate a stable cache key from text content."""
    return f"{prefix}:{hashlib.sha256(text.encode()).hexdigest()}"


# Handler type used for SQLite L2 cache entries for query answers.
QUERY_HANDLER_TYPE = "query"


def get_query_cache_key(query: str) -> str:
    """Build the same cache key that QueryCache would produce for a query-only
    entry (no context_fingerprint)."""
    return generate_cache_key("query", query)


class QueryCache:
    """SQLite-backed query result cache.

    Provides the same API as the previous in-memory version but delegates
    all storage to SQLite (SQLiteCache). This persists across restarts and
    eliminates the need for a separate in-memory tier.
    """

    def __init__(self, max_size: int = None, ttl: int = None):
        # max_size is accepted for backwards compat but ignored — SQLite
        # handles its own storage. TTL is read from settings by SQLiteCache.
        self._ttl = ttl
        self._l2 = None  # Lazily initialized to avoid import-time DB access

    def _get_l2(self):
        """Lazily get the SQLite cache instance."""
        if self._l2 is None:
            from ..db.sqlite_cache import get_sqlite_cache
            self._l2 = get_sqlite_cache()
        return self._l2

    def _build_query_cache_key(self, query: str, context_fingerprint: Optional[str] = None) -> str:
        """Build a stable query-cache key with optional retrieval-context fingerprint."""
        if context_fingerprint:
            key_material = json.dumps(
                {"q": query, "ctx": context_fingerprint},
                ensure_ascii=True,
                sort_keys=True,
            )
        else:
            key_material = query
        return generate_cache_key("query", key_material)

    async def get_result(
        self,
        query: str,
        context_fingerprint: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get cached result for query."""
        key = self._build_query_cache_key(query, context_fingerprint)
        try:
            result = await self._get_l2().get(key, "query")
            if result is not None:
                return result
        except Exception as e:
            logger.debug(f"SQLite cache get failed: {e}")
        return None

    async def set_result(
        self,
        query: str,
        result: Dict[str, Any],
        context_fingerprint: Optional[str] = None,
        ttl: Optional[int] = None,
    ) -> None:
        """Cache result for query."""
        key = self._build_query_cache_key(query, context_fingerprint)
        try:
            settings = get_settings()
            effective_ttl = ttl or self._ttl or getattr(settings, "CACHE_TTL_SECONDS", 86400)
            await self._get_l2().set(key, "query", result, ttl_seconds=effective_ttl)
        except Exception as e:
            logger.debug(f"SQLite cache set failed: {e}")

    async def invalidate(
        self,
        query: str,
        context_fingerprint: Optional[str] = None,
    ) -> bool:
        """Invalidate cached result for query.

        SQLite doesn't support single-key deletion by hash_key alone
        (the clear() method works by handler_type). We work around this
        by setting a zero-length expired entry, which will be naturally
        pruned on the next get. This is a no-op if the entry doesn't exist.
        """
        key = self._build_query_cache_key(query, context_fingerprint)
        try:
            # Overwrite with empty data and TTL of 1 second to effectively
            # invalidate. The next get_result will return None because the
            # entry will have expired.
            await self._get_l2().set(key, "query", {}, ttl_seconds=1)
            return True
        except Exception as e:
            logger.debug(f"SQLite cache invalidate failed: {e}")
            return False

    async def delete(
        self,
        query: str,
        context_fingerprint: Optional[str] = None,
    ) -> bool:
        """Delete cached result for query (alias for invalidate)."""
        return await self.invalidate(query, context_fingerprint)

    async def clear(self) -> None:
        """Clear all cached query results."""
        try:
            await self._get_l2().clear(handler_type="query")
        except Exception as e:
            logger.debug(f"SQLite cache clear failed: {e}")


# Singleton instance used across the runtime
query_cache = QueryCache()
