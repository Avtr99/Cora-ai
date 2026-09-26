"""
Tests for FallbackLLMClient: circuit delegation and SQLite cache attachment.
"""
from unittest.mock import MagicMock

from src.query_processing.fallback_llm_client import FallbackLLMClient


def test_circuit_delegates_to_primary():
    """client.circuit is the primary's circuit breaker."""
    primary = MagicMock()
    fallback = MagicMock()

    client = FallbackLLMClient(primary, fallback)

    assert client.circuit is primary.circuit


def test_attach_sqlite_cache_propagates_to_inner_clients():
    """attach_sqlite_cache sets the wrapper's cache and both inner clients'."""
    primary = MagicMock()
    fallback = MagicMock()
    client = FallbackLLMClient(primary, fallback)
    cache = MagicMock(name="sqlite_cache")

    client.attach_sqlite_cache(cache)

    assert client._sqlite_cache is cache
    primary.attach_sqlite_cache.assert_called_once_with(cache)
    fallback.attach_sqlite_cache.assert_called_once_with(cache)
