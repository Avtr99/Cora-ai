"""Tests for src/db/sqlite_cache.py."""

import asyncio
import pytest
from unittest.mock import patch

from src.db.sqlite_cache import get_sqlite_cache, SQLiteCache


class TestSQLiteCacheSingleton:
    @pytest.mark.asyncio
    async def test_singleton_returns_same_instance(self):
        """Sequential calls must return the same SQLiteCache instance."""
        # Reset singleton for this test.
        from src.db import sqlite_cache as cache_module
        cache_module._sqlite_cache_singleton = None

        first = await get_sqlite_cache()
        second = await get_sqlite_cache()
        assert first is second
        assert isinstance(first, SQLiteCache)

    @pytest.mark.asyncio
    async def test_singleton_survives_concurrent_init(self):
        """Concurrent async callers must all receive the same instance."""
        from src.db import sqlite_cache as cache_module
        cache_module._sqlite_cache_singleton = None

        async def fetch():
            return await get_sqlite_cache()

        # Run many concurrent fetchers to exercise the initialization lock.
        results = await asyncio.gather(*[fetch() for _ in range(20)])
        assert all(r is results[0] for r in results)
        assert isinstance(results[0], SQLiteCache)

    @pytest.mark.asyncio
    async def test_singleton_honors_ttl_setting(self):
        """The singleton should read CACHE_TTL_SECONDS from settings."""
        from src.db import sqlite_cache as cache_module
        cache_module._sqlite_cache_singleton = None

        class _Settings:
            CACHE_TTL_SECONDS = 1234

        # get_settings is imported inside get_sqlite_cache(), so patch the source module.
        with patch("src.config.get_settings", return_value=_Settings()):
            cache = await get_sqlite_cache()

        assert cache.default_ttl_seconds == 1234

    def test_ping_is_async(self):
        """ping() is part of the health-check interface and must be awaitable."""
        cache = SQLiteCache()
        assert asyncio.iscoroutinefunction(cache.ping)
