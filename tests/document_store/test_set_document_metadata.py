"""set_document_metadata replaces the extracted-metadata fields wholesale.

Regression: the metadata fields were persisted through ``update_document``,
whose ``None`` kwargs mean "leave the column alone". A re-extraction that no
longer produced a value (e.g. registry='Gold Standard' on a mislabeled
upload) could never clear the stale column.
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_set_document_metadata_replaces_and_clears(document_store_env):
    from src.document_store.repository import insert_document, set_document_metadata
    from src.document_store.models import DocumentRecord
    from src.document_store.schema import ensure_document_store_tables

    ensure_document_store_tables()
    insert_document(
        DocumentRecord(
            id="doc_meta",
            original_filename="report.md",
            stored_filename="doc_meta.md",
            mime_type="text/markdown",
            extension=".md",
            size_bytes=10,
            sha256="abc",
            status="converting",
            conversion_mode="standard",
            original_path="/tmp/report.md",
            converted_path=None,
            chunk_count=0,
            page_count=None,
            tags=[],
            warnings=[],
            error=None,
            title=None,
            registry=None,
            category=None,
            publisher=None,
            document_id=None,
            version_number=None,
            processing_job_id=None,
        )
    )

    # First extraction labels the document.
    record = set_document_metadata(
        "doc_meta",
        {
            "title": "Gold Standard - Standard & Guidance v1.0",
            "registry": "Gold Standard",
            "category": "Gold Standard",
            "publisher": "Gold Standard",
            "document_id": None,
            "version_number": "1.0",
        },
    )
    assert record.registry == "Gold Standard"
    assert record.publisher == "Gold Standard"

    # Re-extraction with corrected rules: provenance cleared, topic kept.
    record = set_document_metadata(
        "doc_meta",
        {
            "title": "AIM Platform Secretariat - Standard & Guidance v1.0",
            "registry": None,
            "category": "Gold Standard",
            "publisher": "AIM Platform Secretariat",
            "document_id": None,
            "version_number": "1.0",
        },
    )
    assert record.registry is None          # stale value cleared, not kept
    assert record.category == "Gold Standard"
    assert record.publisher == "AIM Platform Secretariat"
    assert record.title == "AIM Platform Secretariat - Standard & Guidance v1.0"


def test_update_document_cannot_write_metadata(document_store_env):
    """update_document no longer accepts metadata kwargs, so a partial write
    that silently leaves sibling fields stale cannot be reintroduced."""
    import inspect

    from src.document_store.repository import update_document

    params = set(inspect.signature(update_document).parameters)
    for field in ("title", "registry", "category", "publisher", "document_id", "version_number"):
        assert field not in params
