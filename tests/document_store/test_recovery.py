"""Tests for document store crash recovery and stale lock cleanup."""
from __future__ import annotations

from io import BytesIO

import pytest
from fastapi import UploadFile


@pytest.mark.asyncio
async def test_recover_interrupted_documents_marks_in_flight_as_failed(document_store_env):
    """Any document left in an in-flight status at startup must be
    flipped to failed so the UI shows a clear error instead of hanging forever.
    Jobs left in queued/processing must also be flipped to failed so the
    document_store_jobs table doesn't accumulate ghost rows.

    In in_process mode (recover_queued_jobs=True, the default), documents still
    at 'queued' (uploaded but never picked up before the crash) are ALSO flipped
    to failed -- otherwise the job is failed but the document stays 'queued'
    forever, leaving the UI stuck with no retry option."""
    from src.document_store.jobs_repo import create_job, get_job, update_job
    from src.document_store.recovery import recover_interrupted_documents
    from src.document_store.repository import (
        get_document_including_deleted,
        update_document,
    )
    from src.document_store.uploads import save_upload

    records = []
    stuck_job_ids = []
    for name, status, job_status in [
        ("stuck-converting.txt", "converting", "processing"),
        ("stuck-indexing.txt", "indexing", "processing"),
        ("stuck-reading.txt", "reading", "processing"),
        ("stuck-deleting.txt", "deleting", "processing"),
        ("stuck-queued-job.txt", "queued", "queued"),
        ("healthy.txt", "indexed", "completed"),
        ("already-failed.txt", "failed", "failed"),
    ]:
        r = await save_upload(
            UploadFile(filename=name, file=BytesIO(f"{name} content".encode())),
            "standard",
            [],
        )
        if status != "queued":
            update_document(r.id, status=status)
        job = create_job(r.id, "process")
        if job_status != "queued":
            update_job(job.id, job_status)
        records.append((r.id, status))
        if job_status in ("queued", "processing"):
            stuck_job_ids.append(job.id)

    recovered = recover_interrupted_documents()
    # 4 in-flight statuses + 1 queued document (in_process mode recovers queued)
    assert recovered == 5

    for doc_id, original_status in records:
        doc = get_document_including_deleted(doc_id)
        assert doc is not None
        if original_status in ("converting", "indexing", "reading", "deleting", "queued"):
            assert doc.status == "failed"
            assert doc.error == "Interrupted by server restart"
        else:
            assert doc.status == original_status

    # Jobs stuck in queued/processing are flipped to failed.
    for job_id in stuck_job_ids:
        job = get_job(job_id)
        assert job is not None
        assert job.status == "failed"
        assert job.error == "Interrupted by server restart"

    # Idempotent: running again recovers nothing.
    assert recover_interrupted_documents() == 0


@pytest.mark.asyncio
async def test_recover_interrupted_documents_preserves_queued_in_worker_mode(document_store_env):
    """In worker mode (recover_queued_jobs=False), documents and jobs at 'queued'
    must be left untouched so the ingest-worker can pick them up after an
    API-container restart. Only 'processing' jobs and in-flight documents are
    recovered."""
    from src.document_store.jobs_repo import create_job, get_job, update_job
    from src.document_store.recovery import recover_interrupted_documents
    from src.document_store.repository import (
        get_document_including_deleted,
        update_document,
    )
    from src.document_store.uploads import save_upload

    # A queued document with a queued job -- must survive worker-mode recovery.
    queued_doc = await save_upload(
        UploadFile(filename="queued.txt", file=BytesIO(b"queued content")),
        "standard",
        [],
    )
    queued_job = create_job(queued_doc.id, "process")  # status='queued' by default

    # An in-flight document with a processing job -- must be recovered.
    stuck_doc = await save_upload(
        UploadFile(filename="stuck.txt", file=BytesIO(b"stuck content")),
        "standard",
        [],
    )
    update_document(stuck_doc.id, status="converting")
    stuck_job = create_job(stuck_doc.id, "process")
    update_job(stuck_job.id, "processing")

    recovered = recover_interrupted_documents(recover_queued_jobs=False)
    assert recovered == 1  # only the converting document

    # Queued document + job preserved for the worker.
    assert get_document_including_deleted(queued_doc.id).status == "queued"
    assert get_job(queued_job.id).status == "queued"

    # In-flight document + job recovered.
    assert get_document_including_deleted(stuck_doc.id).status == "failed"
    assert get_job(stuck_job.id).status == "failed"


def test_recover_interrupted_documents_stale_sweep_only_old_processing(document_store_env):
    """Only processing jobs older than the stale threshold are failed by the sweep."""
    from src.db.database import get_connection
    from src.document_store.jobs_repo import get_job
    from src.document_store.recovery import recover_interrupted_documents
    from src.document_store.schema import ensure_document_store_tables

    ensure_document_store_tables()

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO document_store_documents (
                id, original_filename, stored_filename, mime_type, extension,
                size_bytes, sha256, status, conversion_mode, original_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "doc1",
                "a.md",
                "a.md",
                "text/plain",
                ".md",
                1,
                "sha",
                "reading",
                "standard",
                "/tmp/a.md",
            ),
        )
        conn.execute(
            """
            INSERT INTO document_store_jobs (id, document_id, action, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("job_old", "doc1", "process", "processing", "2024-01-01 00:00:00", "2000-01-01 00:00:00"),
        )
        conn.execute(
            """
            INSERT INTO document_store_jobs (id, document_id, action, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            """,
            ("job_new", "doc1", "process", "processing", "2024-01-01 00:00:00"),
        )
        conn.commit()
    finally:
        conn.close()

    recover_interrupted_documents(stale_processing_threshold_seconds=3600)

    assert get_job("job_old").status == "failed"
    assert get_job("job_new").status == "processing"


def test_release_stale_document_locks_clears_orphaned_lock(document_store_env):
    """A lock pointing at a deleted job row (e.g. via ON DELETE CASCADE) must
    be cleared by the stale-lock sweep, not left permanently set."""
    from src.db.database import get_connection
    from src.document_store.recovery import recover_interrupted_documents
    from src.document_store.repository import get_document_including_deleted
    from src.document_store.schema import ensure_document_store_tables

    ensure_document_store_tables()

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO document_store_documents (
                id, original_filename, stored_filename, mime_type, extension,
                size_bytes, sha256, status, conversion_mode, original_path,
                processing_job_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "doc_orphan",
                "a.md",
                "a.md",
                "text/plain",
                ".md",
                1,
                "sha",
                "indexed",
                "standard",
                "/tmp/a.md",
                "job_missing",
            ),
        )
        # No matching job row exists -- the lock is orphaned.
        conn.commit()
    finally:
        conn.close()

    # recover_interrupted_documents runs the stale-lock sweep; with the old
    # `IN (...)` form this would not match and the lock would stay set.
    recover_interrupted_documents()

    record = get_document_including_deleted("doc_orphan")
    assert record is not None
    assert record.processing_job_id is None
