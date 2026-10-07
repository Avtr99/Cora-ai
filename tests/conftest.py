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
    # Env vars beat the .env file in pydantic-settings, so forcing protection
    # off here keeps a developer's real .env from 401-ing the whole suite.
    # Tests that exercise protection set the flag back on via monkeypatch.
    os.environ["ENABLE_API_KEY_PROTECTION"] = "false"
    # env_ignore_empty turns this into None, so no test ever matches the
    # developer's real key by accident.
    os.environ["API_ACCESS_KEY"] = ""


@pytest.fixture(autouse=True)
def _reset_settings_singleton(monkeypatch):
    """Reset the Settings singleton before each test to avoid stale env values."""
    monkeypatch.setenv("VOYAGE_API_KEY", "test-voyage-api-key")
    monkeypatch.setenv("QDRANT_URL", "http://localhost:6333")
    monkeypatch.setenv("ENABLE_API_KEY_PROTECTION", "false")
    monkeypatch.setenv("API_ACCESS_KEY", "")
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
