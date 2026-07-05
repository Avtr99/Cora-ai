"""
Unified caching module for the RAG system.

Query result caching is backed by SQLite (see src/db/sqlite_cache.py and
the backend_cache table). Agent-level in-memory caches (TTLCache/LRUCache
in routing, rewrite, and conversational handlers) provide short-lived
dedup for rapid-fire requests within a session — they are independent
dedup layers, not a separate cache tier.

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


# Handler type used for SQLite cache entries for query answers.
QUERY_HANDLER_TYPE = "query"


def get_query_cache_key(query: str) -> str:
    """Build the same cache key that QueryCache would produce for a query-only
    entry (no context_fingerprint)."""
    return generate_cache_key("query", query)


class QueryCache:
    """SQLite-backed query result cache.

    Delegates all storage to SQLite (SQLiteCache). Persists across restarts.
    """

    def __init__(self, max_size: int = None, ttl: int = None):
        # max_size is accepted for backwards compat but ignored — SQLite
        # handles its own storage. TTL is read from settings by SQLiteCache.
        self._ttl = ttl
        self._sqlite = None  # Lazily initialized to avoid import-time DB access

    async def _get_sqlite(self):
        """Lazily get the SQLite cache instance."""
        if self._sqlite is None:
            from ..db.sqlite_cache import get_sqlite_cache
            self._sqlite = await get_sqlite_cache()
        return self._sqlite

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
            sqlite = await self._get_sqlite()
            result = await sqlite.get(key, "query")
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
            sqlite = await self._get_sqlite()
            await sqlite.set(key, "query", result, ttl_seconds=effective_ttl)
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
            sqlite = await self._get_sqlite()
            await sqlite.set(key, "query", {}, ttl_seconds=1)
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
            sqlite = await self._get_sqlite()
            await sqlite.clear(handler_type="query")
        except Exception as e:
            logger.debug(f"SQLite cache clear failed: {e}")


# Singleton instance used across the runtime
query_cache = QueryCache()
