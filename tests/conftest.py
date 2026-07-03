"""
Pytest configuration and shared fixtures for Cora API tests.
"""
import os

# Set mock environment variables BEFORE any imports that might trigger Settings
# These are only used in CI/test environments where real credentials aren't available
if not os.environ.get("VOYAGE_API_KEY"):
    os.environ["VOYAGE_API_KEY"] = "test-voyage-api-key"
if not os.environ.get("QDRANT_URL"):
    os.environ["QDRANT_URL"] = "http://localhost:6333"
if not os.environ.get("SECRET_KEY"):
    os.environ["SECRET_KEY"] = "test-secret-key-for-ci-testing"
if not os.environ.get("JWT_SECRET_KEY"):
    os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-for-ci-testing"

import pytest
from typing import List, Dict, Any


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
