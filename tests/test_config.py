"""Behavior-locking tests for the settings schema and validation helpers.

These tests pin down the contract of ``src.config.Settings`` (validators,
derived properties, cached helpers) and ``src.config_validation.normalize_filter_field_name``
*before* the production-quality refactor of ``config.py``. They must pass
unchanged against both the pre- and post-refactor code.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config import Settings
from src.config_validation import normalize_filter_field_name


# ---------------------------------------------------------------------------
# normalize_filter_field_name
# ---------------------------------------------------------------------------

class TestNormalizeFilterFieldName:
    def test_valid_name_passthrough(self):
        assert normalize_filter_field_name("document_id") == "document_id"

    def test_alphanumeric_and_underscore_preserved(self):
        assert normalize_filter_field_name("chunk_index_2") == "chunk_index_2"

    @pytest.mark.parametrize("raw,expected", [
        ("document id", "document_id"),
        ("a/b", "a_b"),
        ("foo-bar", "foo_bar"),
        ("a b/c-d", "a_b_c_d"),
    ])
    def test_separator_replacement(self, raw, expected):
        assert normalize_filter_field_name(raw) == expected

    def test_strips_surrounding_whitespace(self):
        assert normalize_filter_field_name("  doc_id  ") == "doc_id"

    def test_none_raises(self):
        with pytest.raises(ValueError, match="cannot be None"):
            normalize_filter_field_name(None)

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            normalize_filter_field_name("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            normalize_filter_field_name("   ")

    def test_too_long_raises(self):
        long_name = "a" * 65
        with pytest.raises(ValueError, match="exceeds maximum length"):
            normalize_filter_field_name(long_name)

    def test_exactly_max_length_ok(self):
        assert normalize_filter_field_name("a" * 64) == "a" * 64

    def test_disallowed_chars_raise(self):
        with pytest.raises(ValueError, match="disallowed characters"):
            normalize_filter_field_name("doc.id")

    def test_unicode_raises(self):
        with pytest.raises(ValueError, match="disallowed characters"):
            normalize_filter_field_name("docüment")


# ---------------------------------------------------------------------------
# Settings.get_validated_allowed_filter_fields
# ---------------------------------------------------------------------------

class TestGetValidatedAllowedFilterFields:
    def test_parses_default_csv(self):
        settings = Settings()
        fields = settings.get_validated_allowed_filter_fields()
        assert "source" in fields
        assert "document_id" in fields
        assert "chunk_index" in fields
        # No empty strings from trailing commas
        assert "" not in fields

    def test_caches_result(self):
        settings = Settings()
        first = settings.get_validated_allowed_filter_fields()
        second = settings.get_validated_allowed_filter_fields()
        # Same list object => cached
        assert first is second

    def test_resets_cache_when_instance_recreated(self):
        # A fresh instance must not inherit another instance's cache.
        a = Settings()
        b = Settings()
        assert a.get_validated_allowed_filter_fields() is not b.get_validated_allowed_filter_fields()

    def test_custom_fields(self, monkeypatch):
        monkeypatch.setenv("QDRANT_ALLOWED_FILTER_FIELDS", "source, my field, doc-id")
        settings = Settings()
        fields = settings.get_validated_allowed_filter_fields()
        assert fields == ["source", "my_field", "doc_id"]


# ---------------------------------------------------------------------------
# Settings.allowed_document_dirs_resolved
# ---------------------------------------------------------------------------

class TestAllowedDocumentDirsResolved:
    def test_resolves_relative_to_absolute(self):
        settings = Settings()
        resolved = settings.allowed_document_dirs_resolved
        assert len(resolved) == 2  # default "./data,./uploads"
        for path in resolved:
            assert Path(path).is_absolute()

    def test_custom_dirs(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ALLOWED_DOCUMENT_DIRS", str(tmp_path))
        settings = Settings()
        resolved = settings.allowed_document_dirs_resolved
        assert resolved == [str(tmp_path.resolve())]

    def test_skips_empty_entries(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_DOCUMENT_DIRS", "./data,,  ,./uploads")
        settings = Settings()
        resolved = settings.allowed_document_dirs_resolved
        assert len(resolved) == 2


# ---------------------------------------------------------------------------
# Field validators
# ---------------------------------------------------------------------------

class TestValidatePositiveInt:
    def test_positive_passes(self):
        settings = Settings(ASYNC_QUERY_WORKERS=4)
        assert settings.ASYNC_QUERY_WORKERS == 4

    @pytest.mark.parametrize("value", [0, -1])
    def test_non_positive_raises(self, value):
        with pytest.raises(ValidationError) as exc_info:
            Settings(ASYNC_QUERY_WORKERS=value)
        assert "must be a positive integer" in str(exc_info.value)

    def test_applies_to_multiple_fields(self):
        # Spot-check a different field covered by the same validator.
        with pytest.raises(ValidationError):
            Settings(EMBEDDING_BATCH_SIZE=0)


class TestValidatePositiveTimeout:
    def test_positive_passes(self):
        settings = Settings(DOCUMENT_DOCLING_TIMEOUT=60.0)
        assert settings.DOCUMENT_DOCLING_TIMEOUT == 60.0

    @pytest.mark.parametrize("value", [0.0, -1.5])
    def test_non_positive_raises(self, value):
        with pytest.raises(ValidationError) as exc_info:
            Settings(DOCUMENT_DOCLING_TIMEOUT=value)
        assert "must be a positive number" in str(exc_info.value)


class TestValidateSqliteJournalMode:
    @pytest.mark.parametrize("mode", ["DELETE", "TRUNCATE", "PERSIST", "MEMORY", "WAL", "OFF"])
    def test_allowed_modes_pass(self, mode):
        assert Settings(SQLITE_JOURNAL_MODE=mode).SQLITE_JOURNAL_MODE == mode

    @pytest.mark.parametrize("mode", ["wal", "off", "delete"])
    def test_case_insensitive(self, mode):
        assert Settings(SQLITE_JOURNAL_MODE=mode).SQLITE_JOURNAL_MODE == mode.upper()

    def test_invalid_mode_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(SQLITE_JOURNAL_MODE="BOGUS")
        assert "must be one of" in str(exc_info.value)


class TestValidateConversionPromptNotEmpty:
    def test_non_empty_passes(self):
        prompt = "Convert this page to Markdown."
        assert Settings(DOCUMENT_LLM_CONVERSION_PROMPT=prompt).DOCUMENT_LLM_CONVERSION_PROMPT == prompt

    @pytest.mark.parametrize("value", ["", "   ", "\t\n"])
    def test_empty_or_whitespace_raises(self, value):
        with pytest.raises(ValidationError) as exc_info:
            Settings(DOCUMENT_LLM_CONVERSION_PROMPT=value)
        assert "must not be empty" in str(exc_info.value)
