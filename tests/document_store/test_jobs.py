"""Tests for document store job handlers and job claiming."""
from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path
from unittest import mock

import pytest
from fastapi import UploadFile


@pytest.mark.asyncio
async def test_delete_document_job_marks_document_deleted(document_store_env):
    from src.document_store.jobs import delete_document_job
    from src.document_store.repository import get_document, get_document_including_deleted
    from src.document_store.jobs_repo import create_job
    from src.document_store.uploads import save_upload

    upload = UploadFile(filename="delete-me.txt", file=BytesIO(b"Delete me."))
    record = await save_upload(upload, "standard", [])
    job = create_job(record.id, "delete")

    with mock.patch("src.document_store.handlers.delete_document_chunks") as mock_chunks, mock.patch(
        "src.document_store.handlers.remove_document_files"
    ):
        mock_chunks.return_value = None
        await delete_document_job(record.id, job.id)

    updated = get_document(record.id)
    assert updated is None
    deleted = get_document_including_deleted(record.id)
    assert deleted is not None
    assert deleted.status == "deleted"


@pytest.mark.asyncio
async def test_delete_document_job_succeeds_when_already_deleted(document_store_env):
    from src.document_store.jobs import delete_document_job
    from src.document_store.repository import get_document_including_deleted, update_document
    from src.document_store.jobs_repo import create_job
    from src.document_store.uploads import save_upload

    upload = UploadFile(filename="already-deleted.txt", file=BytesIO(b"Already deleted."))
    record = await save_upload(upload, "standard", [])
    update_document(record.id, status="deleted")
    job = create_job(record.id, "delete")

    # The fix ensures Qdrant cleanup runs even for already-soft-deleted docs
    # (previously the job exited early, leaving orphaned chunks behind).
    with mock.patch("src.document_store.handlers.delete_document_chunks") as mock_chunks, mock.patch(
        "src.document_store.handlers.remove_document_files"
    ):
        mock_chunks.return_value = None
        await delete_document_job(record.id, job.id)

    still_deleted = get_document_including_deleted(record.id)
    assert still_deleted is not None
    assert still_deleted.status == "deleted"
    # Qdrant cleanup must run even when the doc was already soft-deleted.
    mock_chunks.assert_called_once_with(record.id)


@pytest.mark.asyncio
async def test_delete_document_job_completes_when_qdrant_cleanup_fails(document_store_env):
    from src.document_store.jobs import delete_document_job
    from src.document_store.repository import get_document, get_document_including_deleted
    from src.document_store.jobs_repo import create_job
    from src.document_store.uploads import save_upload

    upload = UploadFile(filename="qdrant-fail.txt", file=BytesIO(b"Qdrant cleanup fails."))
    record = await save_upload(upload, "standard", [])
    job = create_job(record.id, "delete")

    with mock.patch("src.document_store.handlers.delete_document_chunks") as mock_chunks, mock.patch(
        "src.document_store.handlers.remove_document_files"
    ):
        mock_chunks.side_effect = RuntimeError("Qdrant unavailable")
        await delete_document_job(record.id, job.id)

    updated = get_document(record.id)
    assert updated is None
    deleted = get_document_including_deleted(record.id)
    assert deleted is not None
    assert deleted.status == "deleted"


@pytest.mark.asyncio
async def test_claim_next_job_prioritizes_delete_reindex_process(document_store_env):
    from src.document_store.jobs_repo import claim_next_job, create_job, get_job
    from src.document_store.uploads import save_upload

    contents = [b"doc a", b"doc b", b"doc c"]
    actions = ["process", "reindex", "delete"]
    for i, (content, action) in enumerate(zip(contents, actions)):
        upload = UploadFile(filename=f"doc{i}.md", file=BytesIO(content))
        record = await save_upload(upload, "standard", [])
        create_job(record.id, action, f"{action} job")

    # Delete should be claimed first regardless of creation order.
    claimed = claim_next_job()
    assert claimed is not None
    assert claimed.action == "delete"
    assert get_job(claimed.id).status == "processing"

    claimed = claim_next_job()
    assert claimed is not None
    assert claimed.action == "reindex"

    claimed = claim_next_job()
    assert claimed is not None
    assert claimed.action == "process"

    assert claim_next_job() is None


@pytest.mark.asyncio
async def test_create_job_dedups_queued_same_action(document_store_env):
    from src.document_store.jobs_repo import create_job
    from src.document_store.uploads import save_upload

    upload = UploadFile(filename="doc.md", file=BytesIO(b"unique content"))
    record = await save_upload(upload, "standard", [])
    job1 = create_job(record.id, "process", "first")
    job2 = create_job(record.id, "process", "second")
    assert job1.id == job2.id


@pytest.mark.asyncio
async def test_reindex_document_job_reuses_converted_markdown(document_store_env, tmp_path):
    """Reindex skips reconversion when a converted Markdown file already exists."""
    from src.document_store.jobs import reindex_document_job
    from src.document_store.repository import update_document
    from src.document_store.jobs_repo import create_job
    from src.document_store.uploads import save_upload

    upload = UploadFile(filename="doc.md", file=BytesIO(b"# Hello\n\ncontent"))
    record = await save_upload(upload, "standard", [])
    converted_path = Path(record.converted_path)
    converted_path.parent.mkdir(parents=True, exist_ok=True)
    converted_path.write_text("# Hello\n\ncontent", encoding="utf-8")
    update_document(record.id, converted_path=str(converted_path), status="indexed")

    job = create_job(record.id, "reindex", "reindex")
    with (
        mock.patch("src.document_store.handlers.convert_document") as mock_convert,
        mock.patch("src.document_store.handlers.index_document", return_value=2) as mock_index,
    ):
        await reindex_document_job(record.id, job.id)

    mock_convert.assert_not_called()
    mock_index.assert_called_once()
    indexed_record = mock_index.call_args.args[0]
    assert indexed_record.id == record.id


@pytest.mark.asyncio
async def test_reindex_document_job_reconverts_missing_markdown(document_store_env, tmp_path):
    """Reindex reconverts the original file when the converted Markdown is missing."""
    from src.document_store.converter import ConversionResult
    from src.document_store.jobs import reindex_document_job
    from src.document_store.jobs_repo import create_job
    from src.document_store.uploads import save_upload

    upload = UploadFile(filename="doc.md", file=BytesIO(b"# Hello\n\ncontent"))
    record = await save_upload(upload, "standard", [])
    job = create_job(record.id, "reindex", "reindex")
    result = ConversionResult(markdown="# Converted\n\ncontent", page_count=1)

    with (
        mock.patch("src.document_store.handlers.convert_document", return_value=result) as mock_convert,
        mock.patch("src.document_store.handlers.write_converted_markdown") as mock_write,
        mock.patch("src.document_store.handlers.index_document", return_value=2) as mock_index,
    ):
        await reindex_document_job(record.id, job.id)

    mock_convert.assert_called_once()
    mock_write.assert_called_once()
    mock_index.assert_called_once()


@pytest.mark.asyncio
async def test_process_job_completes_when_document_is_deleting(document_store_env):
    """A process job that starts after the document is marked deleting must not
    run conversion/indexing; it completes cleanly and leaves deletion to the
    delete job."""
    from src.document_store.jobs import process_document_job
    from src.document_store.jobs_repo import create_job, get_job
    from src.document_store.repository import get_document, update_document
    from src.document_store.uploads import save_upload

    upload = UploadFile(filename="doc.md", file=BytesIO(b"# Hello\n\ncontent"))
    record = await save_upload(upload, "standard", [])
    update_document(record.id, status="deleting")
    job = create_job(record.id, "process", "process")

    with mock.patch("src.document_store.handlers.convert_document") as mock_convert:
        await process_document_job(record.id, job.id)

    mock_convert.assert_not_called()
    assert get_job(job.id).status == "completed"
    assert get_document(record.id).status == "deleting"


@pytest.mark.asyncio
async def test_reindex_job_completes_when_document_is_deleted(document_store_env):
    """A reindex job for an already-deleted document completes without work."""
    from src.document_store.jobs import reindex_document_job
    from src.document_store.jobs_repo import create_job, get_job
    from src.document_store.repository import (
        get_document_including_deleted,
        update_document,
    )
    from src.document_store.uploads import save_upload

    upload = UploadFile(filename="doc.md", file=BytesIO(b"# Hello\n\ncontent"))
    record = await save_upload(upload, "standard", [])
    update_document(record.id, status="deleted")
    job = create_job(record.id, "reindex", "reindex")

    with mock.patch("src.document_store.handlers.index_document") as mock_index:
        await reindex_document_job(record.id, job.id)

    mock_index.assert_not_called()
    assert get_job(job.id).status == "completed"
    assert get_document_including_deleted(record.id).status == "deleted"


@pytest.mark.asyncio
async def test_claim_next_job_skips_locked_documents(document_store_env, monkeypatch):
    """A queued job for a document with processing_job_id set is not claimed."""
    from src.config import reset_settings_singleton
    from src.db.database import get_connection
    from src.document_store.jobs_repo import claim_next_job, create_job
    from src.document_store.uploads import save_upload

    monkeypatch.setenv("INGESTION_DISPATCH", "worker")
    reset_settings_singleton()

    upload = UploadFile(filename="doc.md", file=BytesIO(b"doc a"))
    record = await save_upload(upload, "standard", [])
    process_job = create_job(record.id, "process", "process")
    reindex_job = create_job(record.id, "reindex", "reindex")

    # Simulate that a worker is currently processing the document.
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE document_store_documents SET processing_job_id = ? WHERE id = ?",
            (process_job.id, record.id),
        )
        conn.commit()
    finally:
        conn.close()

    # The queued reindex must wait until the lock is released.
    assert claim_next_job() is None

    # After releasing the lock, the queued job can be claimed (delete has
    # priority, then reindex, then process).
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE document_store_documents SET processing_job_id = NULL WHERE id = ?",
            (record.id,),
        )
        conn.commit()
    finally:
        conn.close()

    claimed = claim_next_job()
    assert claimed is not None
    assert claimed.id == reindex_job.id

    reset_settings_singleton()


@pytest.mark.asyncio
async def test_handler_releases_document_lock_after_failure(document_store_env, monkeypatch):
    """A failing handler must release the cross-process document lock."""
    from src.config import reset_settings_singleton
    from src.document_store.jobs import process_document_job
    from src.document_store.jobs_repo import create_job
    from src.document_store.repository import get_document_including_deleted
    from src.document_store.uploads import save_upload

    monkeypatch.setenv("INGESTION_DISPATCH", "in_process")
    reset_settings_singleton()

    upload = UploadFile(filename="doc.pdf", file=BytesIO(b"%PDF-1.4"))
    record = await save_upload(upload, "standard", [])
    job = create_job(record.id, "process", "process")

    with mock.patch(
        "src.document_store.handlers.convert_document",
        side_effect=RuntimeError("conversion failed"),
    ):
        await process_document_job(record.id, job.id)

    updated = get_document_including_deleted(record.id)
    assert updated.processing_job_id is None
    assert updated.status == "failed"
    reset_settings_singleton()


@pytest.mark.asyncio
async def test_process_job_hard_timeout_marks_failed(document_store_env, monkeypatch):
    """A hung conversion that exceeds the hard asyncio timeout is cancelled and
    the document + job are marked failed so the UI allows retry and the worker
    slot + document lock are freed."""
    from src.config import reset_settings_singleton
    from src.document_store.jobs import process_document_job
    from src.document_store.jobs_repo import create_job, get_job
    from src.document_store.repository import get_document_including_deleted
    from src.document_store.uploads import save_upload

    # Tiny timeout so the test runs fast.
    monkeypatch.setenv("DOCUMENT_DOCLING_TIMEOUT", "0.1")
    monkeypatch.setenv("DOCUMENT_JOB_HARD_TIMEOUT_MARGIN_SECONDS", "0.1")
    reset_settings_singleton()

    upload = UploadFile(filename="doc.md", file=BytesIO(b"# Hello\n\ncontent"))
    record = await save_upload(upload, "standard", [])
    job = create_job(record.id, "process", "process")

    async def slow_inner(doc_id, job_id):
        await asyncio.sleep(10)  # far exceeds the 0.2s ceiling

    with mock.patch(
        "src.document_store.handlers._process_document_job_inner",
        side_effect=slow_inner,
    ):
        await process_document_job(record.id, job.id)

    doc = get_document_including_deleted(record.id)
    assert doc.status == "failed"
    assert "hard time limit" in doc.error
    # Lock must be released even after a timeout cancellation.
    assert doc.processing_job_id is None

    job_row = get_job(job.id)
    assert job_row.status == "failed"
    assert "hard time limit" in job_row.error

    reset_settings_singleton()


@pytest.mark.asyncio
async def test_hard_timeout_does_not_clobber_after_sweep_released_lock(
    document_store_env, monkeypatch
):
    """Race condition: if the stuck-job sweep fires before the hard timeout,
    marks the doc failed, and releases the lock, a new job may start. When the
    old task's hard timeout then fires, it must NOT overwrite the new job's
    document status. The timeout handler must check lock ownership first."""
    from src.config import reset_settings_singleton
    from src.db.database import get_connection
    from src.document_store.jobs import process_document_job
    from src.document_store.jobs_repo import create_job, get_job, update_job
    from src.document_store.recovery import recover_interrupted_documents
    from src.document_store.repository import (
        get_document_including_deleted,
        try_acquire_document_lock,
        update_document,
    )
    from src.document_store.uploads import save_upload

    # Give enough ceiling for the test to simulate the sweep before timeout.
    monkeypatch.setenv("DOCUMENT_DOCLING_TIMEOUT", "0.5")
    monkeypatch.setenv("DOCUMENT_JOB_HARD_TIMEOUT_MARGIN_SECONDS", "0.5")
    reset_settings_singleton()

    upload = UploadFile(filename="doc.md", file=BytesIO(b"# Hello\n\ncontent"))
    record = await save_upload(upload, "standard", [])
    old_job = create_job(record.id, "process", "process")

    async def slow_inner(doc_id, job_id):
        # Simulate the sweep firing while the task is hung: mark the job
        # failed, mark the doc failed, and release the lock -- exactly what
        # recover_interrupted_documents does.
        update_job(job_id, "processing")  # set updated_at so sweep can find it
        # Force the job's updated_at into the past so the sweep targets it.
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE document_store_jobs SET updated_at = '2000-01-01 00:00:00' WHERE id = ?",
                (job_id,),
            )
            conn.commit()
        finally:
            conn.close()

        recover_interrupted_documents(
            recover_queued_jobs=False, stale_processing_threshold_seconds=0.01
        )
        # Lock is now released by the sweep. Simulate a new job acquiring it.
        new_job = create_job(doc_id, "process", "process")
        assert try_acquire_document_lock(doc_id, new_job.id) is True
        update_document(doc_id, status="reading", error=None)
        # Now hang until the hard timeout fires.
        await asyncio.sleep(10)

    with mock.patch(
        "src.document_store.handlers._process_document_job_inner",
        side_effect=slow_inner,
    ):
        await process_document_job(record.id, old_job.id)

    doc = get_document_including_deleted(record.id)
    # The new job set status to "reading". The old job's hard timeout must NOT
    # have overwritten it to "failed".
    assert doc.status == "reading", (
        f"Expected 'reading' (new job's status), got '{doc.status}' -- "
        "the hard timeout clobbered a new job after the sweep released the lock"
    )

    # Old job is marked failed by the timeout (that's fine -- it IS the old job).
    old_job_row = get_job(old_job.id)
    assert old_job_row.status == "failed"

    reset_settings_singleton()


@pytest.mark.asyncio
async def test_delete_job_marks_doc_failed_when_final_update_fails(document_store_env):
    """If update_document(status='deleted') fails, the document must be marked
    'failed' (not left stuck in 'deleting') so the UI allows a retry."""
    from src.document_store.jobs import delete_document_job
    from src.document_store.jobs_repo import create_job, get_job
    from src.document_store.repository import (
        get_document_including_deleted,
        update_document as real_update,
    )
    from src.document_store.uploads import save_upload

    upload = UploadFile(filename="doc.md", file=BytesIO(b"# Hello\n\ncontent"))
    record = await save_upload(upload, "standard", [])
    job = create_job(record.id, "delete", "delete")

    # Build a side_effect that fails only for status='deleted' but succeeds
    # for status='failed' (the recovery write inside the except block).
    def selective_update(doc_id, **kwargs):
        if kwargs.get("status") == "deleted":
            raise RuntimeError("DB write failed")
        return real_update(doc_id, **kwargs)

    with (
        mock.patch("src.document_store.handlers.delete_document_chunks", return_value=None),
        mock.patch("src.document_store.handlers.remove_document_files"),
        mock.patch("src.document_store.handlers.update_document", side_effect=selective_update),
    ):
        await delete_document_job(record.id, job.id)

    doc = get_document_including_deleted(record.id)
    assert doc.status == "failed"
    assert "Delete failed" in doc.error

    job_row = get_job(job.id)
    assert job_row.status == "failed"
