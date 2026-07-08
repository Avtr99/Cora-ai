"""Tests for the LLM settings routes (/v1/settings/llm/*)."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from src.api.main import app


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def mock_settings():
    """A minimal Settings-like object for .env detection."""
    class _Settings:
        GEMINI_API_KEY = "gemini-test-key"
        GEMINI_MODEL_MAIN = "gemini-2.5-flash"
        GEMINI_MODEL_LITE = "gemini-2.5-flash-lite"
        OPENAI_API_KEY = None
        OPENROUTER_API_KEY = None

    return _Settings()


@pytest.fixture
def gemini_llm_settings():
    return {
        "provider": "gemini",
        "api_key": "gemini-test-key",
        "base_url": None,
        "model_main": "gemini-2.5-flash",
        "model_lite": "gemini-2.5-flash-lite",
        "model_relevance": None,
        "organization": None,
    }


@pytest.fixture
def openai_llm_settings():
    return {
        "provider": "openai_compatible",
        "api_key": "openai-test-key",
        "base_url": "https://api.openai.com/v1",
        "model_main": "gpt-4.1-mini",
        "model_lite": "gpt-4.1-mini",
        "model_relevance": None,
        "organization": None,
    }


class TestLLMSettingsGet:
    def test_get_llm_config(self, test_client, mock_settings, gemini_llm_settings):
        with patch("src.api.settings_routes.llm.get_llm_settings", return_value=gemini_llm_settings), \
             patch("src.api.settings_routes.llm.is_llm_configured", return_value=True), \
             patch("src.api.settings_routes.llm.get_settings", return_value=mock_settings):
            response = test_client.get("/v1/settings/llm")

        assert response.status_code == 200
        data = response.json()
        assert data["is_configured"] is True
        assert data["provider"] == "gemini"
        assert data["has_api_key"] is True
        assert data["model_main"] == "gemini-2.5-flash"
        assert "api_key" not in data  # API key must never be returned

    def test_get_llm_config_fills_defaults_from_env(self, test_client, mock_settings):
        """When saved settings have no model_main, the route fills from env defaults."""
        settings = {
            "provider": "gemini",
            "api_key": None,
            "base_url": None,
            "model_main": None,
            "model_lite": None,
            "model_relevance": None,
            "organization": None,
        }
        with patch("src.api.settings_routes.llm.get_llm_settings", return_value=settings), \
             patch("src.api.settings_routes.llm.is_llm_configured", return_value=True), \
             patch("src.api.settings_routes.llm.get_settings", return_value=mock_settings):
            response = test_client.get("/v1/settings/llm")

        assert response.status_code == 200
        data = response.json()
        assert data["model_main"] == "gemini-2.5-flash"
        assert data["model_lite"] == "gemini-2.5-flash-lite"


class TestLLMSettingsUpdate:
    def test_update_llm_config(self, test_client, openai_llm_settings):
        payload = {
            "provider": "openai_compatible",
            "api_key": "openai-test-key",
            "base_url": "https://api.openai.com/v1",
            "model_main": "gpt-4.1-mini",
            "model_lite": "gpt-4.1-mini",
        }
        with patch("src.api.settings_routes.llm.save_llm_settings") as mock_save, \
             patch("src.api.settings_routes.llm.get_llm_settings", return_value=openai_llm_settings), \
             patch("src.api.settings_routes.llm.is_llm_configured", return_value=True), \
             patch("src.api.settings_routes.llm._save_profile") as mock_save_profile, \
             patch("src.api.settings_routes.llm.hot_swap_llm_client", new=AsyncMock(return_value={"success": True, "client_type": "OpenAICompatibleClient", "model": "gpt-4.1-mini"})):
            response = test_client.put("/v1/settings/llm", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "openai_compatible"
        assert data["model_main"] == "gpt-4.1-mini"
        mock_save.assert_called_once()
        mock_save_profile.assert_called_once()

    def test_update_llm_config_invalid_provider(self, test_client):
        payload = {"provider": "invalid_provider"}
        response = test_client.put("/v1/settings/llm", json=payload)
        assert response.status_code == 400

    def test_update_llm_config_defaults_base_url(self, test_client, openai_llm_settings):
        """openai_compatible provider without base_url defaults to OpenAI endpoint."""
        payload = {
            "provider": "openai_compatible",
            "api_key": "openai-test-key",
            "model_main": "gpt-4.1-mini",
        }
        with patch("src.api.settings_routes.llm.save_llm_settings") as mock_save, \
             patch("src.api.settings_routes.llm.get_llm_settings", return_value=openai_llm_settings), \
             patch("src.api.settings_routes.llm.is_llm_configured", return_value=True), \
             patch("src.api.settings_routes.llm._save_profile"), \
             patch("src.api.settings_routes.llm.hot_swap_llm_client", new=AsyncMock(return_value={"success": True})):
            response = test_client.put("/v1/settings/llm", json=payload)

        assert response.status_code == 200
        # Verify base_url was defaulted before saving
        saved_kwargs = mock_save.call_args.kwargs
        assert saved_kwargs["base_url"] == "https://api.openai.com/v1"


class TestLLMProviderSwitch:
    def test_switch_to_existing_profile(self, test_client, openai_llm_settings):
        profile = {
            "provider": "openai_compatible",
            "api_key": "openai-test-key",
            "base_url": "https://api.openai.com/v1",
            "model_main": "gpt-4.1-mini",
            "model_lite": "gpt-4.1-mini",
            "model_relevance": None,
            "organization": None,
        }
        with patch("src.api.settings_routes.llm.get_settings"), \
             patch("src.api.settings_routes.llm.get_llm_settings", return_value=openai_llm_settings), \
             patch("src.api.settings_routes.llm._save_profile") as mock_save_profile, \
             patch("src.api.settings_routes.llm._read_profile", return_value=profile) as mock_read_profile, \
             patch("src.api.settings_routes.llm._detect_env_providers", return_value=[]), \
             patch("src.api.settings_routes.llm.save_llm_settings") as mock_save, \
             patch("src.api.settings_routes.llm.save_app_setting"), \
             patch("src.api.settings_routes.llm.hot_swap_llm_client", new=AsyncMock(return_value={"success": True, "client_type": "OpenAICompatibleClient", "model": "gpt-4.1-mini"})):
            response = test_client.post("/v1/settings/llm/switch", json={"label": "openai"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["label"] == "openai"
        assert data["provider"] == "openai_compatible"
        mock_read_profile.assert_called_once_with("openai")
        mock_save.assert_called_once()
        mock_save_profile.assert_called_once()

    def test_switch_to_env_detected_profile(self, test_client, mock_settings, gemini_llm_settings):
        """Switching to a profile only present in .env detection works."""
        with patch("src.api.settings_routes.llm.get_settings", return_value=mock_settings), \
             patch("src.api.settings_routes.llm.get_llm_settings", return_value=gemini_llm_settings), \
             patch("src.api.settings_routes.llm._save_profile"), \
             patch("src.api.settings_routes.llm._read_profile", return_value=None), \
             patch("src.api.settings_routes.llm.save_llm_settings"), \
             patch("src.api.settings_routes.llm.save_app_setting"), \
             patch("src.api.settings_routes.llm.hot_swap_llm_client", new=AsyncMock(return_value={"success": True, "client_type": "GeminiClient", "model": "gemini-2.5-flash"})):
            response = test_client.post("/v1/settings/llm/switch", json={"label": "gemini"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["label"] == "gemini"

    def test_switch_to_missing_profile(self, test_client, gemini_llm_settings):
        with patch("src.api.settings_routes.llm.get_settings"), \
             patch("src.api.settings_routes.llm.get_llm_settings", return_value=gemini_llm_settings), \
             patch("src.api.settings_routes.llm._save_profile"), \
             patch("src.api.settings_routes.llm._read_profile", return_value=None), \
             patch("src.api.settings_routes.llm._detect_env_providers", return_value=[]), \
             patch("src.api.settings_routes.llm.save_llm_settings") as mock_save, \
             patch("src.api.settings_routes.llm.hot_swap_llm_client", new=AsyncMock()):
            response = test_client.post("/v1/settings/llm/switch", json={"label": "nonexistent"})

        assert response.status_code == 400
        mock_save.assert_not_called()

    def test_switch_label_too_long(self, test_client):
        """Pydantic max_length=100 should reject oversized labels."""
        long_label = "a" * 101
        response = test_client.post("/v1/settings/llm/switch", json={"label": long_label})
        assert response.status_code == 422


class TestLLMProvidersList:
    def test_list_available_providers(self, test_client, mock_settings, gemini_llm_settings):
        saved_profiles = {
            "openai": {
                "provider": "openai_compatible",
                "api_key": "openai-test-key",
                "base_url": "https://api.openai.com/v1",
                "model_main": "gpt-4.1-mini",
                "model_lite": "gpt-4.1-mini",
            }
        }
        with patch("src.api.settings_routes.llm.get_settings", return_value=mock_settings), \
             patch("src.api.settings_routes.llm.get_llm_settings", return_value=gemini_llm_settings), \
             patch("src.api.settings_routes.llm._read_all_profiles", return_value=saved_profiles):
            response = test_client.get("/v1/settings/llm/providers")

        assert response.status_code == 200
        data = response.json()
        assert data["current"] == "gemini"
        slugs = {p["slug"] for p in data["available"]}
        assert "gemini" in slugs
        assert "openai" in slugs


class TestLLMModelsList:
    def test_list_ollama_models(self, test_client):
        models_response = {
            "models": [
                {"name": "llama3", "size": 1000, "details": {"parameter_size": "8B", "family": "llama"}}
            ]
        }
        # Patch the symbols as imported into the route module.
        with patch("src.api.settings_routes.llm._validate_ollama_url", return_value="http://localhost:11434"), \
             patch("src.api.settings_routes.llm._list_ollama_models", return_value=models_response):
            response = test_client.get("/v1/settings/llm/models?base_url=http://localhost:11434")

        assert response.status_code == 200

    def test_list_models_non_ollama_returns_empty(self, test_client):
        """A non-local URL should yield an empty list without making an outbound request."""
        response = test_client.get("/v1/settings/llm/models?base_url=https://api.openai.com/v1")
        assert response.status_code == 200
        data = response.json()
        assert data["models"] == []

    def test_list_models_missing_base_url(self, test_client):
        # FastAPI validates the required query parameter before the route handler runs.
        response = test_client.get("/v1/settings/llm/models")
        assert response.status_code == 422


class TestLLMConnectionTest:
    def test_test_gemini_config(self, test_client):
        # Patch the symbol as imported into the route module.
        with patch("src.api.settings_routes.llm._test_gemini", return_value={"success": True, "message": "OK", "detail": None}) as mock_test:
            response = test_client.post("/v1/settings/llm/test", json={
                "provider": "gemini",
                "api_key": "test-key",
                "model_main": "gemini-2.5-flash",
            })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_test.assert_called_once()

    def test_test_openai_config(self, test_client):
        with patch("src.api.settings_routes.llm._test_openai_compatible", return_value={"success": True, "message": "OK", "detail": None}) as mock_test:
            response = test_client.post("/v1/settings/llm/test", json={
                "provider": "openai_compatible",
                "api_key": "test-key",
                "base_url": "https://api.openai.com/v1",
                "model_main": "gpt-4.1-mini",
            })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_test.assert_called_once()

    def test_test_invalid_provider(self, test_client):
        response = test_client.post("/v1/settings/llm/test", json={
            "provider": "invalid",
            "api_key": "test-key",
        })
        assert response.status_code == 400
