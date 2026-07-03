import os

# Set mock environment variables BEFORE importing modules that require Settings
if not os.environ.get("VOYAGE_API_KEY"):
    os.environ["VOYAGE_API_KEY"] = "test-voyage-api-key"
if not os.environ.get("QDRANT_URL"):
    os.environ["QDRANT_URL"] = "http://localhost:6333"
if not os.environ.get("SECRET_KEY"):
    os.environ["SECRET_KEY"] = "test-secret-key-for-ci-testing"
if not os.environ.get("JWT_SECRET_KEY"):
    os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-for-ci-testing"

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
import uuid
from datetime import datetime, timezone

from src.api.main import app

@pytest.fixture
def test_client():
    return TestClient(app)

@pytest.fixture
def mock_process_query_core():
    """Mock process_query_core to return actual response data."""
    def mock_side_effect(*args, **kwargs):
        # Return actual data, not AsyncMock
        return {
            "answer": "Test answer",
            "confidence": 0.9,
            "sources": ["knowledge_base"],
            "conversation_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "citations": None,
            "reasoning_steps": None,
            "metadata": None,
            "quiz": None,
        }
    
    with patch('src.api.main.process_query_core', side_effect=mock_side_effect) as mock:
        yield mock

class TestAPI:
    def test_health_check(self, test_client):
        """Test health check endpoint"""
        from unittest.mock import patch
        
        # Mock the Qdrant health check to return healthy
        with patch('src.api.main.run_health_checks') as mock_run_checks:
            mock_run_checks.return_value = {
                "status": "healthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "components": {
                    "qdrant": {"status": "healthy"}
                }
            }
            
            response = test_client.get("/health")
            assert response.status_code == 200
            data = response.json()
            # Health check should return 'healthy' or 'degraded' (if other services fail)
            assert data["status"] in ["healthy", "degraded"]
            assert "timestamp" in data

    def test_add_documents_not_implemented(self, test_client):
        """Test that document ingestion endpoints are removed"""
        response = test_client.post(
            "/documents/batch",
            json={"documents": [{"text": "test"}]}
        )
        # Endpoint is fully removed — FastAPI returns 405 (Method Not Allowed)
        # since no route matches POST /documents/batch.
        assert response.status_code in (404, 405)

    def test_process_query_success(
        self,
        test_client,
        mock_process_query_core
    ):
        """Test successful query processing"""
        mocked_response = {
            "answer": "Test answer",
            "confidence": 0.9,
            "sources": ["knowledge_base"],
            "conversation_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "citations": None,
            "reasoning_steps": None,
            "metadata": None,
            "quiz": None,
        }
        mock_process_query_core.return_value = mocked_response
        
        response = test_client.post(
            "/query",
            json={"text": "What are carbon credits?"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "confidence" in data
        assert "sources" in data
        assert "conversation_id" in data
        assert "timestamp" in data

    def test_process_query_with_conversation_id(
        self,
        test_client,
        mock_process_query_core
    ):
        """Test query processing with provided conversation ID"""
        conv_id = str(uuid.uuid4())
        
        def mock_with_conversation_id(*args, **kwargs):
            # Preserve the conversation_id from the request
            return {
                "answer": "Test answer",
                "confidence": 0.9,
                "sources": ["knowledge_base"],
                "conversation_id": conv_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "citations": None,
                "reasoning_steps": None,
                "metadata": None,
                "quiz": None,
            }
        
        mock_process_query_core.side_effect = mock_with_conversation_id
        
        response = test_client.post(
            "/query",
            json={
                "text": "What are carbon credits?",
                "conversation_id": conv_id
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["conversation_id"] == conv_id

    def test_process_query_forwards_history_to_orchestrator(self, test_client):
        """Regression: root /query must pass history into orchestrator path."""
        mocked_response = {
            "answer": "Test answer",
            "confidence": 0.9,
            "sources": ["knowledge_base"],
            "conversation_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "citations": None,
            "reasoning_steps": None,
            "metadata": None,
            "quiz": None,
        }

        with patch("src.api.main.process_query_core", new=AsyncMock(return_value=mocked_response)) as mock_core:
            response = test_client.post(
                "/query",
                json={
                    "text": "Can you summarize that?",
                    "history": [
                        {"role": "user", "content": "What is additionality?"},
                        {"role": "assistant", "content": "Additionality means reductions would not happen otherwise."},
                    ],
                },
            )

            assert response.status_code == 200
            assert mock_core.await_count == 1

            await_args = mock_core.await_args
            called_query = await_args.args[0] if await_args.args else await_args.kwargs.get("query")
            include_history_flag = await_args.kwargs.get("include_chat_history_in_orchestrator")

            assert called_query is not None
            assert called_query.history is not None
            assert len(called_query.history) == 2
            assert include_history_flag is True

    def test_stream_query_forwards_history_to_orchestrator(self, test_client):
        """Regression: /query/stream must pass history into streaming pipeline."""

        async def mock_stream(*args, **kwargs):
            yield {"event": "status", "status": "accepted"}
            yield {"event": "done"}

        with patch("src.api.main.process_query_core_stream", side_effect=mock_stream) as mock_stream_fn:
            response = test_client.post(
                "/query/stream",
                json={
                    "text": "Can you summarize that?",
                    "history": [
                        {"role": "user", "content": "What is additionality?"},
                        {
                            "role": "assistant",
                            "content": "Additionality means reductions would not happen otherwise.",
                        },
                    ],
                },
            )
            list(response.iter_lines())

            assert response.status_code == 200
            assert mock_stream_fn.call_count == 1

            call_args = mock_stream_fn.call_args
            called_query = call_args.args[0] if call_args.args else call_args.kwargs.get("query")
            include_history_flag = call_args.kwargs.get("include_chat_history_in_orchestrator")

            assert called_query is not None
            assert called_query.history is not None
            assert len(called_query.history) == 2
            assert include_history_flag is True

    def test_process_query_validation(self, test_client, mock_process_query_core):
        """Test query validation"""
        # Test with empty query - should return 422 for validation error
        response = test_client.post(
            "/query",
            json={"text": ""}
        )
        assert response.status_code == 422

        # Test with missing text field - should return 422 for validation error
        response = test_client.post(
            "/query",
            json={"invalid": "format"}
        )
        assert response.status_code == 422

    def test_error_handling(
        self,
        test_client,
        mock_process_query_core
    ):
        """Test error handling in query processing"""
        error_message = "Test error"
        mock_process_query_core.side_effect = Exception(error_message)
        
        response = test_client.post(
            "/query",
            json={"text": "What are carbon credits?"}
        )
        
        assert response.status_code == 500
        data = response.json()
        assert data.get("error") == "int"
        assert data.get("error_code") == "INT_001"
        assert data.get("message", "").startswith("Internal server error processing query (error_id: ")

    def test_concurrent_requests(
        self,
        test_client,
        mock_process_query_core
    ):
        """Test handling of concurrent requests"""
        mocked_response = {
            "answer": "Test answer",
            "confidence": 0.9,
            "sources": ["knowledge_base"],
            "conversation_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "citations": None,
            "reasoning_steps": None,
            "metadata": None,
            "quiz": None,
        }
        mock_process_query_core.return_value = mocked_response
        
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(
                    test_client.post,
                    "/query",
                    json={"text": f"Query {i}"}
                )
                for i in range(5)
            ]
            responses = [f.result() for f in futures]
        
        # Assert all requests were successful
        assert all(r.status_code == 200 for r in responses)
        # Each response should have unique conversation_id
        conv_ids = [r.json()["conversation_id"] for r in responses]
        assert len(set(conv_ids)) == len(responses)

    def test_config_status_returns_chat_readiness_fields(self, test_client):
        """GET /api/v1/settings/status returns chat_ready/kb_ready/search_ready."""
        with patch("src.api.settings_routes.status.get_llm_settings") as mock_llm_settings, \
             patch("src.api.settings_routes.status.is_llm_configured", return_value=True), \
             patch("src.api.settings_routes.status.get_settings") as mock_get_settings:

            mock_llm_settings.return_value = {
                "provider": "gemini",
                "api_key": "test-key",
                "model_main": "gemini-2.5-flash",
                "model_lite": "gemini-2.5-flash-lite",
                "base_url": None,
                "organization": None,
            }

            settings = mock_get_settings.return_value
            settings.EMBEDDING_PROVIDER = "voyage"
            settings.EMBEDDING_MODEL = "voyage-4-lite"
            settings.EMBEDDING_DIM = 1024
            settings.VOYAGE_API_KEY = "test-voyage-key"
            settings.RERANK_PROVIDER = "none"
            settings.RERANK_MODEL = None
            settings.SEARCH_PROVIDER = "tavily"
            settings.TAVILY_API_KEY = "test-tavily-key"
            settings.QDRANT_URL = "http://localhost:6333"
            settings.QDRANT_COLLECTION = "cora"

            # Mock Qdrant collection info with 5 indexed points.
            vectors = type("Vectors", (), {"size": 1024})()
            params = type("Params", (), {"vectors": vectors})()
            config = type("Config", (), {"params": params})()
            mock_collection_info = type("CollectionInfo", (), {
                "config": config,
                "points_count": 5,
            })()
            mock_client = type("MockClient", (), {
                "get_collection": lambda self, name: mock_collection_info,
                "close": lambda self: None,
            })()

            with patch("qdrant_client.QdrantClient", return_value=mock_client):
                response = test_client.get("/api/v1/settings/status")

        assert response.status_code == 200
        data = response.json()
        assert "chat_ready" in data
        assert "kb_ready" in data
        assert "search_ready" in data
        assert data["kb_ready"] is True
        assert data["search_ready"] is True
        assert data["chat_ready"] is True
