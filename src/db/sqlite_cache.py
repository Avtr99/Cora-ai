import asyncio
import json
import logging
from typing import Optional, Dict, Any
from ..db.database import get_connection

logger = logging.getLogger(__name__)

class SQLiteCache:
    """Persistent cache backed by local SQLite.

    Stores query results, routing decisions, and rewrite results in the
    backend_cache table. Survives application restarts.
    """

    def __init__(self, default_ttl_seconds: int = 86400):
        self.default_ttl_seconds = default_ttl_seconds

    @property
    def enabled(self) -> bool:
        return True

    def _get(self, hash_key: str, handler_type: str) -> Optional[Dict[str, Any]]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT cached_data
                FROM backend_cache
                WHERE hash_key = ?
                  AND handler_type = ?
                  AND datetime(expires_at) > datetime('now')
                """,
                (hash_key, handler_type)
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row['cached_data'])
            return None
        except Exception as e:
            logger.warning(f"SQLiteCache.get failed: {e}")
            return None
        finally:
            conn.close()

    async def get(self, hash_key: str, handler_type: str) -> Optional[Dict[str, Any]]:
        return await asyncio.to_thread(self._get, hash_key, handler_type)

    def _set(self, hash_key: str, handler_type: str, data: Dict[str, Any], ttl_seconds: Optional[int] = None) -> bool:
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO backend_cache (hash_key, handler_type, cached_data, expires_at)
                VALUES (?, ?, ?, datetime('now', '+' || ? || ' seconds'))
                ON CONFLICT(hash_key, handler_type)
                DO UPDATE SET
                    cached_data=excluded.cached_data,
                    expires_at=excluded.expires_at
                """,
                (hash_key, handler_type, json.dumps(data), ttl)
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning(f"SQLiteCache.set failed: {e}")
            return False
        finally:
            conn.close()

    async def set(self, hash_key: str, handler_type: str, data: Dict[str, Any], ttl_seconds: Optional[int] = None) -> bool:
        return await asyncio.to_thread(self._set, hash_key, handler_type, data, ttl_seconds)

    def _clear(self, handler_type: Optional[str] = None) -> bool:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            if handler_type:
                cursor.execute("DELETE FROM backend_cache WHERE handler_type = ?", (handler_type,))
            else:
                cursor.execute("DELETE FROM backend_cache")
            conn.commit()
            return True
        except Exception as e:
            logger.warning(f"SQLiteCache.clear failed: {e}")
            return False
        finally:
            conn.close()

    async def clear(self, handler_type: Optional[str] = None) -> bool:
        return await asyncio.to_thread(self._clear, handler_type)

    def _ping(self) -> bool:
        """Lightweight connectivity check for the SQLite cache table."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS row_count FROM backend_cache")
            cursor.fetchone()
            return True
        except Exception as e:
            logger.warning(f"SQLiteCache ping failed: {e}")
            return False
        finally:
            conn.close()

    async def ping(self) -> bool:
        return await asyncio.to_thread(self._ping)


_sqlite_cache_singleton: Optional[SQLiteCache] = None
_sqlite_cache_lock = asyncio.Lock()


async def get_sqlite_cache() -> SQLiteCache:
    """Get the shared SQLiteCache singleton.

    All callers (query cache, orchestrator, lifespan, indexer, health check)
    share the same instance so read and write paths are consistent.
    """
    global _sqlite_cache_singleton
    if _sqlite_cache_singleton is not None:
        return _sqlite_cache_singleton
    async with _sqlite_cache_lock:
        if _sqlite_cache_singleton is not None:
            return _sqlite_cache_singleton
        from ..config import get_settings
        settings = get_settings()
        ttl = int(getattr(settings, "CACHE_TTL_SECONDS", 86400))
        _sqlite_cache_singleton = SQLiteCache(default_ttl_seconds=ttl)
    return _sqlite_cache_singleton
