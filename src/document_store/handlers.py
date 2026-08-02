"""Job handlers for process, reindex, and delete actions.

Each handler acquires the cross-process document lock, runs its inner body
under a hard asyncio timeout (so a hung conversion cannot hold a worker slot
or lock forever), and releases the lock in a ``finally`` block. The inner
bodies call the converter, write markdown, persist VCM metadata, and index
into Qdrant.

Tests patch the imported names (``convert_document``, ``index_document``,
``delete_document_chunks``, ``remove_document_files``, ``update_document``,
``write_converted_markdown``, ``_process_document_job_inner``) by targeting
``src.document_store.handlers.<name>`` -- the handlers reference these as bare
names, so Python resolves them in this module's namespace at call time.
``jobs.py`` re-exports the public handler functions so existing
``from src.document_store.jobs import process_document_job`` import sites keep
working.
"""

from __future__ import annotations

from typing import Awaitable, Callable, Optional

import asyncio
import time
from pathlib import Path

from loguru import logger

from ..config import get_settings
from .converter import convert_document, write_converted_markdown
from .docling_warmup import _maybe_emit_docling_download_notice
from .errors import _classify_conversion_error
from .indexer import delete_document_chunks, index_document
from .ingestion_pool import _get_ingestion_sem
from .logging_utils import _log_ingestion_stage
from .models import DocumentRecord
from .storage import (
    get_document,
    get_document_including_deleted,
    release_document_lock,
    remove_document_files,
    try_acquire_document_lock,
    update_document,
    update_job,
)
# Imported as a module so handlers can mutate the process-level warmed flag via
# attribute access (``docling_warmup._docling_models_warmed = True``). A bare
# ``from .docling_warmup import _docling_models_warmed`` would bind a local
# copy and the write would not be visible to other importers.
from . import docling_warmup


def _refresh_record(document_id: str, job_id: str) -> Optional[DocumentRecord]:
    """Reload a document record; mark the job failed if the document is gone.

    If the document is being deleted or has already been deleted, complete the
    current job cleanly so that a delete does not race with an in-flight
    process/reindex. The delete job owns the final "deleted" status.
    """
    record = get_document(document_id)
    if record is None:
        # Check if the record was already deleted (e.g. duplicate delete job).
        existing = get_document_including_deleted(document_id)
        if existing is not None and existing.status == "deleted":
            update_job(job_id, "completed", message="Document already deleted")
        else:
            update_job(job_id, "failed", error="Document not found")
        return None
    if record.status in ("deleting", "deleted"):
        message = (
            "Document is being deleted"
            if record.status == "deleting"
            else "Document already deleted"
        )
        update_job(job_id, "completed", message=message)
        return None
    return record


async def _acquire_document_lock(document_id: str, job_id: str, action: str) -> bool:
    """Acquire the cross-process document lock for this job.

    In worker mode the attempt is non-blocking: if another job holds the lock
    the job is re-queued so another worker can try again later. In in-process
    mode it waits up to ``DOCUMENT_DOCLING_TIMEOUT + 60s``.

    If the document is being deleted (or already deleted) and this job is not a
    delete, the job is completed without running.
    """
    settings = get_settings()
    is_worker = settings.INGESTION_DISPATCH == "worker"
    wait_timeout = settings.DOCUMENT_DOCLING_TIMEOUT + 60.0
    poll_interval = 0.5

    start = time.perf_counter()
    while True:
        record = get_document_including_deleted(document_id)
        if record is None:
            update_job(job_id, "completed", message="Document not found")
            return False
        if record.status in ("deleting", "deleted") and action != "delete":
            message = (
                "Document is being deleted"
                if record.status == "deleting"
                else "Document already deleted"
            )
            update_job(job_id, "completed", message=message)
            return False

        acquired = await asyncio.to_thread(try_acquire_document_lock, document_id, job_id)
        if acquired:
            return True

        if is_worker:
            # Don't hold a worker slot waiting; requeue and try again later.
            update_job(job_id, "queued", message="Waiting for another job on this document")
            return False

        if time.perf_counter() - start > wait_timeout:
            update_job(job_id, "failed", error="Could not acquire document lock: timeout")
            return False

        await asyncio.sleep(poll_interval)


async def _run_job_with_hard_timeout(
    inner: Callable[[str, str], Awaitable[None]],
    document_id: str,
    job_id: str,
) -> None:
    """Wrap a job handler body in a hard asyncio timeout.

    A hung Docling/embedding call cannot hold a worker slot or per-document
    lock forever: if the handler exceeds
    ``DOCUMENT_DOCLING_TIMEOUT + DOCUMENT_JOB_HARD_TIMEOUT_MARGIN_SECONDS``,
    the coroutine is cancelled and the document + job are marked failed so the
    UI allows retry.

    Note: ``asyncio.wait_for`` cancels the coroutine but cannot kill a thread
    blocked in ``asyncio.to_thread`` (e.g. Docling's CPU-bound parsing). The
    orphaned thread may continue in the background, but the worker slot and
    document lock are freed immediately -- which is what matters for availability.
    """
    settings = get_settings()
    ceiling = (
        float(settings.DOCUMENT_DOCLING_TIMEOUT)
        + float(settings.DOCUMENT_JOB_HARD_TIMEOUT_MARGIN_SECONDS)
    )
    try:
        await asyncio.wait_for(inner(document_id, job_id), timeout=ceiling)
    except asyncio.TimeoutError:
        logger.error(
            "Job {} (doc={}) exceeded hard timeout of {}s — cancelling",
            job_id, document_id, ceiling,
        )
        user_error = (
            f"Conversion/indexing exceeded the hard time limit ({int(ceiling)}s). "
            "Try a smaller document, increase DOCUMENT_DOCLING_TIMEOUT, "
            "or switch to llm_api mode."
        )
        # Only mark the document as failed if we still hold its lock. If the
        # stuck-job sweep already marked the job failed and released the lock,
        # a new job may have started — clobbering its status would corrupt
        # the new job's progress. The old job is always safe to mark failed
        # (it's identified by job_id, not document_id).
        record = get_document_including_deleted(document_id)
        if record is not None and record.processing_job_id == job_id:
            update_document(document_id, status="failed", error=user_error)
        update_job(job_id, "failed", error=user_error)


async def process_document_job(document_id: str, job_id: str) -> None:
    if not await _acquire_document_lock(document_id, job_id, "process"):
        return
    try:
        async with _get_ingestion_sem():
            await _run_job_with_hard_timeout(
                _process_document_job_inner, document_id, job_id
            )
    finally:
        await asyncio.to_thread(release_document_lock, document_id, job_id)


async def _process_document_job_inner(document_id: str, job_id: str) -> None:
    update_job(job_id, "processing", "Reading document")
    record = _refresh_record(document_id, job_id)
    if record is None:
        return
    try:
        update_document(document_id, status="reading", error=None)
        _maybe_emit_docling_download_notice(job_id, record)

        start = time.perf_counter()
        result = await convert_document(record)
        _log_ingestion_stage("job", "conversion", document_id, job_id, time.perf_counter() - start)
        docling_warmup._docling_models_warmed = True

        record = _refresh_record(document_id, job_id)
        if record is None:
            return

        start = time.perf_counter()
        write_converted_markdown(record, result)
        _log_ingestion_stage("job", "markdown_writing", document_id, job_id, time.perf_counter() - start)

        # Persist the VCM metadata extracted during conversion so the indexer
        # and RAG pipeline read from a single source of truth.
        start = time.perf_counter()
        meta = result.metadata
        record = update_document(
            document_id,
            title=meta.get("title"),
            registry=meta.get("registry"),
            category=meta.get("category"),
            publisher=meta.get("publisher"),
            document_id=meta.get("document_id"),
            version_number=meta.get("version_number"),
        )
        _log_ingestion_stage("job", "metadata_extraction", document_id, job_id, time.perf_counter() - start)

        update_job(job_id, "processing", "Adding document to Cora")
        record = _refresh_record(document_id, job_id)
        if record is None:
            return
        start = time.perf_counter()
        chunk_count = await index_document(record, job_id=job_id)
        _log_ingestion_stage("job", "indexing", document_id, job_id, time.perf_counter() - start, chunk_count)
        update_job(job_id, "completed", f"Ready to use. {chunk_count} text sections added.")
    except Exception as exc:
        logger.exception("Document processing failed for {}", document_id)
        user_error = _classify_conversion_error(exc, record.conversion_mode if record else "standard")
        # Only mark the document failed if we still hold the lock — the sweep
        # may have already released it and a new job may have started.
        current = get_document_including_deleted(document_id)
        if current is not None and current.processing_job_id == job_id:
            update_document(document_id, status="failed", error=user_error)
        update_job(job_id, "failed", error=user_error)


async def reindex_document_job(document_id: str, job_id: str) -> None:
    if not await _acquire_document_lock(document_id, job_id, "reindex"):
        return
    try:
        async with _get_ingestion_sem():
            await _run_job_with_hard_timeout(
                _reindex_document_job_inner, document_id, job_id
            )
    finally:
        await asyncio.to_thread(release_document_lock, document_id, job_id)


async def _reindex_document_job_inner(document_id: str, job_id: str) -> None:
    update_job(job_id, "processing", "Refreshing document for Cora")
    record = _refresh_record(document_id, job_id)
    if record is None:
        return
    try:
        if not record.converted_path or not Path(record.converted_path).exists():
            _maybe_emit_docling_download_notice(job_id, record)
            start = time.perf_counter()
            result = await convert_document(record)
            _log_ingestion_stage("job", "conversion", document_id, job_id, time.perf_counter() - start)
            docling_warmup._docling_models_warmed = True

            record = _refresh_record(document_id, job_id)
            if record is None:
                return

            start = time.perf_counter()
            write_converted_markdown(record, result)
            _log_ingestion_stage("job", "markdown_writing", document_id, job_id, time.perf_counter() - start)

            # Persist freshly extracted VCM metadata.
            start = time.perf_counter()
            meta = result.metadata
            record = update_document(
                document_id,
                title=meta.get("title"),
                registry=meta.get("registry"),
                category=meta.get("category"),
                publisher=meta.get("publisher"),
                document_id=meta.get("document_id"),
                version_number=meta.get("version_number"),
            )
            _log_ingestion_stage("job", "metadata_extraction", document_id, job_id, time.perf_counter() - start)
            record = _refresh_record(document_id, job_id)
            if record is None:
                return
        else:
            # Even on reindex without reconversion, re-read metadata from the
            # record so the indexer gets the persisted values.
            record = _refresh_record(document_id, job_id)
            if record is None:
                return
        start = time.perf_counter()
        chunk_count = await index_document(record, job_id=job_id)
        _log_ingestion_stage("job", "indexing", document_id, job_id, time.perf_counter() - start, chunk_count)
        update_job(job_id, "completed", f"Document refreshed. {chunk_count} text sections added.")
    except Exception as exc:
        logger.exception("Document re-index failed for {}", document_id)
        user_error = _classify_conversion_error(exc, record.conversion_mode if record else "standard")
        current = get_document_including_deleted(document_id)
        if current is not None and current.processing_job_id == job_id:
            update_document(document_id, status="failed", error=user_error)
        update_job(job_id, "failed", error=user_error)


async def delete_document_job(document_id: str, job_id: str) -> None:
    if not await _acquire_document_lock(document_id, job_id, "delete"):
        return
    try:
        update_job(job_id, "processing", "Deleting document")
        # Use get_document_including_deleted so we can still clean up Qdrant chunks
        # for a document that was already soft-deleted by a prior (possibly failed)
        # delete attempt. _refresh_record would return None for soft-deleted docs
        # (get_document filters status != 'deleted'), causing us to exit before
        # vector store cleanup — leaving orphaned chunks in Qdrant.
        record = get_document_including_deleted(document_id)
        if record is None:
            update_job(job_id, "failed", error="Document not found")
            return
        already_deleted = record.status == "deleted"
        if not already_deleted:
            try:
                update_document(document_id, status="deleting", error=None)
            except Exception as exc:
                logger.warning("Could not mark document {} as deleting: {}", document_id, exc)

        # Always run Qdrant cleanup — it's idempotent (deleting non-existent
        # points is a no-op) and is the only way to purge orphaned chunks left
        # behind by a previous failed delete.
        qdrant_error = None
        try:
            await delete_document_chunks(document_id)
        except Exception as exc:
            logger.exception("Vector store deletion failed for {}", document_id)
            qdrant_error = str(exc)

        try:
            remove_document_files(record)
        except Exception:
            logger.exception("Local file deletion failed for {}", document_id)

        try:
            update_document(document_id, status="deleted", error=None)
            if already_deleted:
                message = "Document already deleted"
            else:
                message = "Document deleted"
            if qdrant_error:
                message = f"{message}; vector store cleanup failed: {qdrant_error}"
            update_job(job_id, "completed", message=message)
        except Exception as exc:
            logger.exception("Could not mark document {} as deleted", document_id)
            # Mark the document as failed so the UI allows a retry instead of
            # leaving it stuck in 'deleting' forever — but only if we still
            # hold the lock (the sweep may have released it).
            current = get_document_including_deleted(document_id)
            if current is not None and current.processing_job_id == job_id:
                try:
                    update_document(
                        document_id, status="failed", error=f"Delete failed: {exc}"
                    )
                except Exception:
                    logger.exception(
                        "Could not mark document {} as failed after delete failure",
                        document_id,
                    )
            update_job(job_id, "failed", error=str(exc))
    finally:
        await asyncio.to_thread(release_document_lock, document_id, job_id)
