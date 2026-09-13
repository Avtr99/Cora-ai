"""Shared fixtures for the document store test package."""
from __future__ import annotations

import pytest

from src.document_store.models import DocumentRecord


@pytest.fixture
def make_record():
    """Return a DocumentRecord factory with sensible test defaults."""
    defaults = {
        "id": "doc_test",
        "original_filename": "test.pdf",
        "stored_filename": "test.pdf",
        "mime_type": "application/pdf",
        "extension": ".pdf",
        "size_bytes": 100,
        "sha256": "sha",
        "status": "indexed",
        "conversion_mode": "standard",
        "original_path": "/tmp/test.pdf",
        "converted_path": None,
        "chunk_count": 0,
        "page_count": None,
        "tags": [],
        "warnings": [],
        "error": None,
        "title": None,
        "registry": None,
        "category": None,
        "publisher": None,
        "document_id": None,
        "version_number": None,
        "processing_job_id": None,
        "created_at": None,
        "updated_at": None,
    }

    def _make_record(**overrides):
        return DocumentRecord(**{**defaults, **overrides})

    return _make_record
