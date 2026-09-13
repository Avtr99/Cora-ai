"""Tests for the document store repository (record CRUD and metadata sidecar)."""
from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile


@pytest.mark.asyncio
async def test_update_document_skips_sidecar_for_transient_status(document_store_env):
    """update_document must only rewrite the metadata sidecar on
    terminal statuses, not on every transient state transition."""
    from src.document_store.repository import update_document
    from src.document_store.uploads import save_upload

    record = await save_upload(
        UploadFile(filename="sidecar.txt", file=BytesIO(b"sidecar test")),
        "standard",
        [],
    )
    sidecar = Path(record.original_path).parent.parent / "metadata" / f"{record.id}.json"
    assert sidecar.exists()  # written once by save_upload
    original_mtime = sidecar.stat().st_mtime_ns

    # Transient transition -- should NOT rewrite the sidecar.
    update_document(record.id, status="converting")
    assert sidecar.stat().st_mtime_ns == original_mtime

    # Terminal transition -- should rewrite the sidecar.
    update_document(record.id, status="indexed", chunk_count=3)
    assert sidecar.stat().st_mtime_ns != original_mtime
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert data["status"] == "indexed"
    assert data["chunk_count"] == 3
