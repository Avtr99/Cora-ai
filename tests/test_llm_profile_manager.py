"""Tests for src/db/llm_profile_manager.py."""

import json
from unittest.mock import patch, MagicMock

from src.db.llm_profile_manager import (
    _profile_key,
    _read_all_profiles,
    _read_profile,
    _save_profile,
    _slug,
    _label_for_openai,
    _detect_env_providers,
)


class TestProfileKey:
    def test_profile_key_prefix(self):
        assert _profile_key("gemini") == "llm_profile_gemini"


class TestSlug:
    def test_slug_normalizes_label(self):
        assert _slug("OpenAI") == "openai"
        assert _slug("Open Router") == "open_router"
        assert _slug("My (Custom) Provider") == "my_custom_provider"


class TestLabelForOpenAI:
    def test_openai_host(self):
        assert _label_for_openai("https://api.openai.com/v1") == "OpenAI"

    def test_openrouter_host(self):
        assert _label_for_openai("https://openrouter.ai/api/v1") == "OpenRouter"

    def test_ollama_host(self):
        assert _label_for_openai("http://localhost:11434") == "Ollama"

    def test_evil_host_not_mislabeled(self):
        """A host like openai.com.evil.com should not be labeled 'OpenAI'."""
        assert _label_for_openai("https://openai.com.evil.com/v1") == "Custom"

    def test_custom_host(self):
        assert _label_for_openai("https://example.com/v1") == "Custom"


class TestDetectEnvProviders:
    def test_detect_gemini(self):
        class _Settings:
            GEMINI_API_KEY = "gemini-key"
            GEMINI_MODEL_MAIN = "gemini-2.5-flash"
            GEMINI_MODEL_LITE = "gemini-2.5-flash-lite"
            OPENAI_API_KEY = None
            OPENROUTER_API_KEY = None

        providers = _detect_env_providers(_Settings())
        assert len(providers) == 1
        assert providers[0]["slug"] == "gemini"

    def test_detect_all_providers(self):
        class _Settings:
            GEMINI_API_KEY = "gemini-key"
            GEMINI_MODEL_MAIN = "gemini-2.5-flash"
            GEMINI_MODEL_LITE = "gemini-2.5-flash-lite"
            OPENAI_API_KEY = "openai-key"
            OPENROUTER_API_KEY = "openrouter-key"

        providers = _detect_env_providers(_Settings())
        slugs = {p["slug"] for p in providers}
        assert slugs == {"gemini", "openai", "openrouter"}


class TestReadAllProfiles:
    def test_malformed_profile_row_is_skipped(self):
        """Regression: a single malformed JSON row must not hide all profiles."""
        valid_value = json.dumps({"provider": "gemini", "api_key": "k"})
        rows = [
            {"key": "llm_profile_gemini", "value": valid_value},
            {"key": "llm_profile_corrupt", "value": "not-json"},
        ]

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.return_value.fetchall.return_value = rows
        mock_conn.cursor.return_value = mock_cursor

        with patch("src.db.llm_profile_manager.get_connection", return_value=mock_conn):
            profiles = _read_all_profiles()

        assert "gemini" in profiles
        assert "corrupt" not in profiles

    def test_all_profiles_returned_when_valid(self):
        rows = [
            {"key": "llm_profile_gemini", "value": json.dumps({"provider": "gemini"})},
            {"key": "llm_profile_openai", "value": json.dumps({"provider": "openai_compatible"})},
        ]

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.return_value.fetchall.return_value = rows
        mock_conn.cursor.return_value = mock_cursor

        with patch("src.db.llm_profile_manager.get_connection", return_value=mock_conn):
            profiles = _read_all_profiles()

        assert set(profiles.keys()) == {"gemini", "openai"}


class TestReadProfile:
    def test_read_profile_returns_none_when_missing(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.return_value.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cursor

        with patch("src.db.llm_profile_manager.get_connection", return_value=mock_conn):
            assert _read_profile("missing") is None

    def test_read_profile_returns_parsed_dict(self):
        value = json.dumps({"provider": "gemini", "api_key": "k"})
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.return_value.fetchone.return_value = {"value": value}
        mock_conn.cursor.return_value = mock_cursor

        with patch("src.db.llm_profile_manager.get_connection", return_value=mock_conn):
            profile = _read_profile("gemini")

        assert profile["provider"] == "gemini"


class TestSaveProfile:
    def test_save_profile_persists_json(self):
        with patch("src.db.llm_profile_manager.save_app_setting") as mock_save:
            _save_profile("gemini", "gemini", "key", None, "m1", "m2", "m3", "org")

        mock_save.assert_called_once()
        key_arg, value_arg = mock_save.call_args.args
        assert key_arg == "llm_profile_gemini"
        saved = json.loads(value_arg)
        assert saved["provider"] == "gemini"
        assert saved["api_key"] == "key"
