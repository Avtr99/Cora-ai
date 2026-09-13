"""Tests for document upload saving and tag/filename helpers."""
from __future__ import annotations

import os
from io import BytesIO

import pytest
from fastapi import UploadFile


@pytest.mark.asyncio
async def test_save_upload_persists_original_and_metadata(document_store_env):
    from src.document_store.repository import get_document, list_documents
    from src.document_store.uploads import save_upload

    upload = UploadFile(filename="Policy Draft.md", file=BytesIO(b"# Policy\n\nCarbon market text."))
    record = await save_upload(upload, "standard", ["policy", "client-a"])

    assert record.id.startswith("doc_")
    assert record.original_filename == "Policy_Draft.md"
    assert record.status == "queued"
    assert os.path.exists(record.original_path)
    assert os.path.exists(document_store_env / "documents" / "metadata" / f"{record.id}.json")

    stored = get_document(record.id)
    assert stored is not None
    assert stored.tags == ["policy", "client-a"]
    assert [doc.id for doc in list_documents()] == [record.id]


@pytest.mark.asyncio
async def test_save_upload_rejects_duplicate_sha256(document_store_env):
    from src.document_store.uploads import save_upload

    content = b"# Duplicate\n\nSame content."
    first = await save_upload(
        UploadFile(filename="original.md", file=BytesIO(content)),
        "standard",
        [],
    )
    with pytest.raises(FileExistsError):
        await save_upload(
            UploadFile(filename="copy.md", file=BytesIO(content)),
            "standard",
            [],
        )
    assert first.sha256


def test_parse_tags_deduplicates_and_limits_values():
    from src.document_store.uploads import parse_tags

    assert parse_tags('["Legal", "legal", " Client-A "]') == ["legal", "client-a"]
    assert parse_tags("Policy, Methodology, policy") == ["policy", "methodology"]


@pytest.mark.asyncio
async def test_docx_uploads_are_rejected(document_store_env):
    """DOCX is no longer an accepted format."""
    from src.document_store.uploads import save_upload

    with pytest.raises(ValueError, match="Unsupported file type"):
        await save_upload(
            UploadFile(filename="report.docx", file=BytesIO(b"PK\x03\x04docx content")),
            "standard",
            [],
        )


@pytest.mark.asyncio
async def test_html_uploads_are_rejected(document_store_env):
    """HTML is no longer an accepted format."""
    from src.document_store.uploads import save_upload

    with pytest.raises(ValueError, match="Unsupported file type"):
        await save_upload(
            UploadFile(filename="page.html", file=BytesIO(b"<html><body>content</body></html>")),
            "standard",
            [],
        )
