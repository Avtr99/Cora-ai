"""
Unified caching module for the RAG system.

Query result caching is backed by SQLite (see src/db/sqlite_cache.py and
the backend_cache table). Agent-level in-memory caches (TTLCache/LRUCache
in routing, rewrite, and conversational handlers) provide short-lived
dedup for rapid-fire requests within a session — they are independent
dedup layers, not a separate cache tier.

Embedding persistence also lives in SQLite (see embedding_cache table
in migrations/001_initial.sql).

Cache key material
------------------
The query-cache key folds in every input that can change the answer so a
stale entry is never served after a config or corpus change:

- the normalized query (always present),
- an optional retrieval-context fingerprint,
- ``config_revision`` — bumped on any embedding/reranker/LLM model change,
- ``corpus_revision`` — bumped once per ingestion batch,
- ``config_version`` — bumped on every ``reload_settings()`` call so cached
  responses do not serve a stale config-version stamp,
- the embedding provider+model+dim and reranker provider+model (read from
  the in-memory Settings singleton — no DB hit on the hot path).

``corpus_revision``, ``config_revision`` and ``config_version`` are read from
the DB on each key build. The extra SELECT is negligible compared to Qdrant + LLM work,
and it keeps the app process from serving stale keys after a worker
ingestion bump.

A revision bump changes the key, so stale entries are skipped automatically;
``clear()`` is still called on config changes to reclaim the space.
"""
import hashlib
import json
import logging
from typing import Any, Dict, Optional

from ..config import get_settings
from ..db.revisions import get_revisions

logger = logging.getLogger(__name__)


def generate_cache_key(prefix: str, text: str) -> str:
    """Generate a stable cache key from text content."""
    return f"{prefix}:{hashlib.sha256(text.encode()).hexdigest()}"


def get_query_cache_key(query: str) -> str:
    """Build the same cache key that QueryCache would produce for a query-only
    entry (no context_fingerprint)."""
    return query_cache.build_cache_key(query, context_fingerprint=None)


class QueryCache:
    """SQLite-backed query result cache.

    Delegates all storage to SQLite (SQLiteCache). Persists across restarts.
    Revision counters are read from the DB on every key build so the app
    process never keeps a stale corpus/config snapshot.
    """

    def __init__(self, max_size: Optional[int] = None, ttl: Optional[int] = None):
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

    def _model_fingerprint(self) -> Dict[str, Any]:
        """Embedding + reranker model fingerprint from the Settings singleton.

        Read from the in-memory singleton (no DB hit). The LLM model is covered
        by ``config_revision`` instead, to avoid a DB read on the hot path.
        """
        settings = get_settings()
        return {
            "emb": {
                "p": getattr(settings, "EMBEDDING_PROVIDER", None),
                "m": getattr(settings, "EMBEDDING_MODEL", None),
                "d": getattr(settings, "EMBEDDING_DIM", None),
            },
            "rer": {
                "p": getattr(settings, "RERANK_PROVIDER", None),
                "m": getattr(settings, "RERANK_MODEL", None),
            },
        }

    def build_cache_key(
        self, query: str, context_fingerprint: Optional[str] = None
    ) -> str:
        """Build a stable query-cache key.

        Folds the query, optional retrieval-context fingerprint, corpus +
        config revisions, config version, and the embedding/reranker model
        fingerprint into a single ``json.dumps(..., sort_keys=True)`` block so
        any of those changing produces a different key (invalidating stale
        entries).

        Revisions/version are read from the DB each call; the extra round-trip
        is negligible compared to Qdrant + LLM work, and it removes the stale
        in-memory snapshot bug in the split app/ingest-worker stack.
        """
        revisions = get_revisions()
        key_material = json.dumps(
            {
                "q": query,
                "ctx": context_fingerprint,
                "cfg": revisions.get("config_revision", 0),
                "corp": revisions.get("corpus_revision", 0),
                "ver": revisions.get("config_version", 0),
                "models": self._model_fingerprint(),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
        return generate_cache_key("query", key_material)

    def _build_query_cache_key(
        self, query: str, context_fingerprint: Optional[str] = None
    ) -> str:
        """Backwards-compatible alias for :meth:`build_cache_key`."""
        return self.build_cache_key(query, context_fingerprint=context_fingerprint)

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


async def invalidate_query_cache_for_config_change() -> None:
    """Bump ``config_revision`` and clear stale query-cache entries.

    Call this after any Settings UI save that changes the embedding, reranker,
    or answer-generation LLM model. The revision bump changes the cache key
    material (so stale entries are skipped even if ``clear()`` races with a
    concurrent request), and ``clear()`` reclaims the space.

    ``build_cache_key`` reads revisions from the DB each call, so the next
    query will see the new revision even if ``clear()`` is still running.
    """
    try:
        from ..db.revisions import bump_config_revision
        bump_config_revision()
    except Exception as e:
        logger.warning("Failed to bump config_revision: %s", e)
    await query_cache.clear()


# Singleton instance used across the runtime
query_cache = QueryCache()
