"""
Pytest configuration and shared fixtures for Cora API tests.
"""
import os

import pytest
from typing import List, Dict, Any

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


@pytest.fixture
def sample_documents() -> List[Dict[str, Any]]:
    """
    Sample documents for testing document batch operations.
    
    Returns:
        List of document dictionaries with text and metadata.
    """
    return [
        {
            "text": "Carbon credits are certificates representing emission reductions.",
            "metadata": {"source": "doc1.pdf", "category": "basics"}
        },
        {
            "text": "The Gold Standard is a certification for carbon offset projects.",
            "metadata": {"source": "doc2.pdf", "category": "standards"}
        },
        {
            "text": "Verra VCS is one of the largest voluntary carbon credit programs.",
            "metadata": {"source": "doc3.pdf", "category": "standards"}
        }
    ]


@pytest.fixture
def sample_vector_results() -> Dict[str, Any]:
    """
    Sample vector store results for testing query processing.
    
    Returns:
        Dictionary with documents and metadatas matching Qdrant/Vector store format.
    """
    return {
        "documents": [
            "Carbon credits are certificates representing emission reductions.",
            "Companies can trade carbon credits in voluntary markets.",
            "Each credit equals one ton of CO2 reduction."
        ],
        "metadatas": [
            {"parent_doc": "doc1.pdf", "summary": "About carbon credits"},
            {"parent_doc": "doc2.pdf", "summary": "Trading markets"},
            {"parent_doc": "doc1.pdf", "summary": "CO2 reduction"}
        ],
        "distances": [0.1, 0.2, 0.3]
    }


@pytest.fixture
def sample_query() -> str:
    """Sample query for testing."""
    return "What are carbon credits?"


@pytest.fixture
def sample_conversation_id() -> str:
    """Sample conversation ID for testing."""
    import uuid
    return str(uuid.uuid4())
