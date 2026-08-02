"""Tests for the embeddings/reranker settings routes.

Covers the P0 fix: embeddings and reranker must NOT share API keys via a
single DB row. Before the fix, both routes wrote to ``voyage_api_key`` /
``cohere_api_key``, so the last writer won and the other subsystem silently
used the wrong key.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock

from src.api.main import app


@pytest.fixture
def test_client():
    return TestClient(app)


class TestSharedApiKeyIsolation:
    """The shared-key cross-contamination bug: embeddings and reranker must
    keep independent API keys.

    Before the fix, both routes wrote to the same ``voyage_api_key`` /
    ``cohere_api_key`` DB key. Saving embeddings with key A then reranker
    with key B silently overwrote the embeddings key. These tests pin the
    fix: each subsystem reads its own scoped DB key.
    """

    def test_embeddings_voyage_key_does_not_overwrite_reranker_key(self, test_client):
        """Saving embeddings with key A and reranker with key B leaves each
        subsystem reading its own key.

        The test captures the DB writes from each PUT and asserts the key
        namespaces are disjoint — the embeddings write must not touch the
        reranker's key and vice versa.
        """
        saved_keys: dict = {}

        def fake_save(settings_dict):
            saved_keys.update(settings_dict)

        # GET returns a configured state so the PUT response model is happy.
        def fake_get_settings():
            s = MagicMock()
            s.EMBEDDING_PROVIDER = "voyage"
            s.EMBEDDING_MODEL = "voyage-4-lite"
            s.EMBEDDING_DIM = 1024
            s.OLLAMA_BASE_URL = "http://localhost:11434"
            s.RERANK_PROVIDER = "voyage"
            s.RERANK_MODEL = "rerank-2.5"
            # Each subsystem reads its OWN scoped key.
            s.EMBEDDING_VOYAGE_API_KEY = "emb-key-A"
            s.RERANKER_VOYAGE_API_KEY = "rerank-key-B"
            return s

        with patch("src.api.settings_routes.embeddings.save_app_settings", side_effect=fake_save), \
             patch("src.api.settings_routes.reranker.save_app_settings", side_effect=fake_save), \
             patch("src.api.settings_routes.embeddings.get_settings", side_effect=fake_get_settings), \
             patch("src.api.settings_routes.reranker.get_settings", side_effect=fake_get_settings), \
             patch("src.api.settings_routes.embeddings.reload_settings"), \
             patch("src.api.settings_routes.reranker.reload_settings"), \
             patch("src.api.settings_routes.embeddings.invalidate_query_cache_for_config_change", new=AsyncMock()), \
             patch("src.api.settings_routes.reranker.invalidate_query_cache_for_config_change", new=AsyncMock()), \
             patch("src.api.settings_routes.embeddings.embedding_has_api_key", return_value=True), \
             patch("src.api.settings_routes.reranker.reranker_has_api_key", return_value=True):
            # Save embeddings with key A
            r1 = test_client.put("/v1/settings/embeddings", json={
                "provider": "voyage", "api_key": "emb-key-A",
            })
            assert r1.status_code == 200, r1.text
            # Save reranker with key B
            r2 = test_client.put("/v1/settings/reranker", json={
                "provider": "voyage", "api_key": "rerank-key-B",
            })
            assert r2.status_code == 200, r2.text

        # The embeddings write must use the embedding-scoped key, NOT the
        # shared key the reranker also writes.
        assert saved_keys.get("embedding_voyage_api_key") == "emb-key-A", \
            "embeddings must write to embedding_voyage_api_key, not the shared voyage_api_key"
        assert saved_keys.get("reranker_voyage_api_key") == "rerank-key-B", \
            "reranker must write to reranker_voyage_api_key, not the shared voyage_api_key"
        # The shared key must NOT be written by either route.
        assert "voyage_api_key" not in saved_keys, \
            "neither route should write the shared voyage_api_key — that is the bug"

    def test_embeddings_cohere_key_does_not_overwrite_reranker_key(self, test_client):
        """Same isolation check for the Cohere provider."""
        saved_keys: dict = {}

        def fake_save(settings_dict):
            saved_keys.update(settings_dict)

        def fake_get_settings():
            s = MagicMock()
            s.EMBEDDING_PROVIDER = "cohere"
            s.EMBEDDING_MODEL = "embed-english-v3"
            s.EMBEDDING_DIM = 1024
            s.OLLAMA_BASE_URL = "http://localhost:11434"
            s.RERANK_PROVIDER = "cohere"
            s.RERANK_MODEL = "rerank-english-v3.0"
            s.EMBEDDING_COHERE_API_KEY = "emb-cohere-A"
            s.RERANKER_COHERE_API_KEY = "rerank-cohere-B"
            return s

        with patch("src.api.settings_routes.embeddings.save_app_settings", side_effect=fake_save), \
             patch("src.api.settings_routes.reranker.save_app_settings", side_effect=fake_save), \
             patch("src.api.settings_routes.embeddings.get_settings", side_effect=fake_get_settings), \
             patch("src.api.settings_routes.reranker.get_settings", side_effect=fake_get_settings), \
             patch("src.api.settings_routes.embeddings.reload_settings"), \
             patch("src.api.settings_routes.reranker.reload_settings"), \
             patch("src.api.settings_routes.embeddings.invalidate_query_cache_for_config_change", new=AsyncMock()), \
             patch("src.api.settings_routes.reranker.invalidate_query_cache_for_config_change", new=AsyncMock()), \
             patch("src.api.settings_routes.embeddings.embedding_has_api_key", return_value=True), \
             patch("src.api.settings_routes.reranker.reranker_has_api_key", return_value=True):
            test_client.put("/v1/settings/embeddings", json={
                "provider": "cohere", "api_key": "emb-cohere-A",
            })
            test_client.put("/v1/settings/reranker", json={
                "provider": "cohere", "api_key": "rerank-cohere-B",
            })

        assert saved_keys.get("embedding_cohere_api_key") == "emb-cohere-A"
        assert saved_keys.get("reranker_cohere_api_key") == "rerank-cohere-B"
        assert "cohere_api_key" not in saved_keys, \
            "neither route should write the shared cohere_api_key — that is the bug"

    def test_embeddings_openai_key_uses_scoped_key(self, test_client):
        """OpenAI key for embeddings must be scoped (embeddings-only)."""
        saved_keys: dict = {}

        def fake_save(settings_dict):
            saved_keys.update(settings_dict)

        def fake_get_settings():
            s = MagicMock()
            s.EMBEDDING_PROVIDER = "openai"
            s.EMBEDDING_MODEL = "text-embedding-3-small"
            s.EMBEDDING_DIM = 1024
            s.OLLAMA_BASE_URL = "http://localhost:11434"
            s.EMBEDDING_OPENAI_API_KEY = "emb-openai-A"
            return s

        with patch("src.api.settings_routes.embeddings.save_app_settings", side_effect=fake_save), \
             patch("src.api.settings_routes.embeddings.get_settings", side_effect=fake_get_settings), \
             patch("src.api.settings_routes.embeddings.reload_settings"), \
             patch("src.api.settings_routes.embeddings.invalidate_query_cache_for_config_change", new=AsyncMock()), \
             patch("src.api.settings_routes.embeddings.embedding_has_api_key", return_value=True):
            r = test_client.put("/v1/settings/embeddings", json={
                "provider": "openai", "api_key": "emb-openai-A",
            })
            assert r.status_code == 200, r.text

        assert saved_keys.get("embedding_openai_api_key") == "emb-openai-A"
        assert "openai_api_key" not in saved_keys, \
            "embeddings must not write the shared openai_api_key — that collides with the LLM subsystem"

    def test_embedding_has_api_key_reads_scoped_voyage_key(self):
        """The has_api_key helper reads the embedding-scoped key first, falling
        back to the shared .env key. This pins the read path of the fix:
        a scoped key alone is sufficient; the shared key is a fallback."""
        from src.api.settings_routes.helpers import embedding_has_api_key

        # Scoped key set, shared key unset -> configured
        s = MagicMock()
        s.EMBEDDING_PROVIDER = "voyage"
        s.EMBEDDING_VOYAGE_API_KEY = "emb-key"
        s.VOYAGE_API_KEY = None
        assert embedding_has_api_key(s) is True

        # Scoped key unset, shared key set -> still configured (env fallback)
        s.EMBEDDING_VOYAGE_API_KEY = None
        s.VOYAGE_API_KEY = "shared-key"
        assert embedding_has_api_key(s) is True, \
            "embedding_has_api_key must fall back to the shared VOYAGE_API_KEY for .env-only operators"

        # Both unset -> not configured
        s.EMBEDDING_VOYAGE_API_KEY = None
        s.VOYAGE_API_KEY = None
        assert embedding_has_api_key(s) is False

    def test_reranker_has_api_key_reads_scoped_voyage_key(self):
        """Same pin for the reranker read path: scoped key first, env fallback."""
        from src.api.settings_routes.helpers import reranker_has_api_key

        s = MagicMock()
        s.RERANK_PROVIDER = "voyage"
        s.RERANKER_VOYAGE_API_KEY = "rerank-key"
        s.VOYAGE_API_KEY = None
        assert reranker_has_api_key(s) is True

        s.RERANKER_VOYAGE_API_KEY = None
        s.VOYAGE_API_KEY = "shared-key"
        assert reranker_has_api_key(s) is True, \
            "reranker_has_api_key must fall back to the shared VOYAGE_API_KEY for .env-only operators"

        s.RERANKER_VOYAGE_API_KEY = None
        s.VOYAGE_API_KEY = None
        assert reranker_has_api_key(s) is False

