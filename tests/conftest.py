"""
Pytest configuration and shared fixtures for Cora API tests.
"""
import os

import pytest

from src.config import reset_settings_singleton


def pytest_configure(config):
    """Set deterministic test environment variables before any test imports."""
    # Required to satisfy the pytest hookspec signature; not used here.
    _ = config
    os.environ["VOYAGE_API_KEY"] = "test-voyage-api-key"
    os.environ["QDRANT_URL"] = "http://localhost:6333"
    os.environ["SECRET_KEY"] = "test-secret-key-for-ci-testing"
    os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-for-ci-testing"


@pytest.fixture(autouse=True)
def _reset_settings_singleton(monkeypatch):
    """Reset the Settings singleton before each test to avoid stale env values."""
    monkeypatch.setenv("VOYAGE_API_KEY", "test-voyage-api-key")
    monkeypatch.setenv("QDRANT_URL", "http://localhost:6333")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-ci-testing")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-key-for-ci-testing")
    reset_settings_singleton()
