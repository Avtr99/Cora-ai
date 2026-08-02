"""Tests for LLM client model-name sanitization."""

from types import SimpleNamespace
from unittest.mock import patch

from src.query_processing.gemini_client import GeminiClient
from src.query_processing.openai_client import OpenAICompatibleClient
from src.query_processing.llm_factory import _create_single_client


def _empty_settings():
    """Return a Settings-like object with no LLM model overrides."""
    return SimpleNamespace()


class TestGeminiClientModelSanitization:
    """Gemini client must reject model IDs from other providers."""

    @patch("src.query_processing.gemini_client.get_settings", return_value=_empty_settings())
    def test_uses_valid_short_model(self, _mock):
        client = GeminiClient(api_key="test", model_main="gemini-2.5-flash")
        assert client.model_main == "gemini-2.5-flash"

    @patch("src.query_processing.gemini_client.get_settings", return_value=_empty_settings())
    def test_uses_valid_models_path(self, _mock):
        client = GeminiClient(api_key="test", model_main="models/gemini-2.5-flash")
        assert client.model_main == "models/gemini-2.5-flash"

    @patch("src.query_processing.gemini_client.get_settings", return_value=_empty_settings())
    def test_falls_back_for_openrouter_prefixed_model(self, _mock):
        client = GeminiClient(
            api_key="test",
            model_main="google/gemini-2.5-flash",
            model_lite="google/gemini-2.5-flash",
        )
        assert client.model_main == "gemini-2.5-flash"
        assert client.model_lite == "gemini-2.5-flash-lite"

    @patch("src.query_processing.gemini_client.get_settings", return_value=_empty_settings())
    def test_falls_back_for_gpt_model(self, _mock):
        client = GeminiClient(api_key="test", model_main="gpt-4.1-mini")
        assert client.model_main == "gemini-2.5-flash"


class TestOpenAICompatibleClientModelSanitization:
    """OpenAI-compatible client must reject bare Gemini API model names."""

    @patch("src.query_processing.openai_client.get_settings", return_value=_empty_settings())
    def test_uses_valid_openai_model(self, _mock):
        client = OpenAICompatibleClient(api_key="test", model_main="gpt-4.1-mini")
        assert client.model_main == "gpt-4.1-mini"

    @patch("src.query_processing.openai_client.get_settings", return_value=_empty_settings())
    def test_uses_valid_openrouter_model(self, _mock):
        client = OpenAICompatibleClient(
            api_key="test",
            base_url="https://openrouter.ai/api/v1",
            model_main="google/gemini-2.5-flash",
        )
        assert client.model_main == "google/gemini-2.5-flash"

    @patch("src.query_processing.openai_client.get_settings", return_value=_empty_settings())
    def test_falls_back_for_bare_gemini_on_openrouter(self, _mock):
        client = OpenAICompatibleClient(
            api_key="test",
            base_url="https://openrouter.ai/api/v1",
            model_main="gemini-2.5-flash",
        )
        assert client.model_main == "google/gemini-2.5-flash"

    @patch("src.query_processing.openai_client.get_settings", return_value=_empty_settings())
    def test_falls_back_for_bare_gemini_on_openai(self, _mock):
        client = OpenAICompatibleClient(
            api_key="test",
            base_url="https://api.openai.com/v1",
            model_main="gemini-2.5-flash",
        )
        assert client.model_main == "gpt-4.1-mini"


class TestLLMFactoryModelSanitization:
    """The factory passes sanitized model names into clients."""

    @patch("src.query_processing.gemini_client.get_settings", return_value=_empty_settings())
    def test_create_single_client_sanitizes_gemini_stale_openrouter_model(self, _mock):
        client = _create_single_client(
            {
                "provider": "gemini",
                "api_key": "test",
                "base_url": None,
                "model_main": "google/gemini-2.5-flash",
                "model_lite": "google/gemini-2.5-flash",
                "model_relevance": None,
                "organization": None,
            }
        )
        assert client.model_main == "gemini-2.5-flash"
        assert client.model_lite == "gemini-2.5-flash-lite"

    @patch("src.query_processing.openai_client.get_settings", return_value=_empty_settings())
    def test_create_single_client_sanitizes_openai_bare_gemini_model(self, _mock):
        client = _create_single_client(
            {
                "provider": "openai_compatible",
                "api_key": "test",
                "base_url": "https://openrouter.ai/api/v1",
                "model_main": "gemini-2.5-flash",
                "model_lite": "gemini-2.5-flash-lite",
                "model_relevance": None,
                "organization": None,
            }
        )
        assert client.model_main == "google/gemini-2.5-flash"
        assert client.model_lite == "google/gemini-2.5-flash"
