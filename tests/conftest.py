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


@pytest.fixture()
def document_store_env(tmp_path, monkeypatch):
    """Set up an isolated in-memory document store for one test."""
    data_dir = tmp_path / "data"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'cora.db'}")
    monkeypatch.setenv("DOCUMENT_STORE_ROOT", str(data_dir / "documents"))
    monkeypatch.setenv("ALLOWED_DOCUMENT_DIRS", str(data_dir))
    monkeypatch.setenv("DOCUMENT_ALLOWED_EXTENSIONS", ".pdf,.md,.txt,.csv,.json,.jsonl")
    monkeypatch.setenv("DOCUMENT_UPLOAD_MAX_BYTES", str(1024 * 1024))
    reset_settings_singleton()
    yield data_dir
    reset_settings_singleton()
