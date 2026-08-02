"""Crash recovery and stale document-lock cleanup.

Called once at startup (and periodically by the ingest worker) to reconcile
the ``document_store_documents`` and ``document_store_jobs`` tables after an
ungraceful shutdown: in-flight documents are flipped to ``failed`` so the UI
shows a retry option instead of a permanently stuck status, and document
locks held by dead/missing jobs are released.
"""

from __future__ import annotations

import sqlite3
from typing import Optional

from ..db.database import get_connection
from .schema import _INTERRUPTED_STATUSES


def _release_stale_document_locks(conn: sqlite3.Connection) -> int:
    """Clear document locks held by jobs that are no longer processing, or whose
    job row has been deleted (e.g. by ``ON DELETE CASCADE``). Without the
    ``NOT IN`` form, an orphaned ``processing_job_id`` pointing at a missing
    job row would never be cleared -- permanently locking the document.
    """
    cursor = conn.execute(
        """
        UPDATE document_store_documents
        SET processing_job_id = NULL, updated_at = CURRENT_TIMESTAMP
        WHERE processing_job_id IS NOT NULL
          AND processing_job_id NOT IN (
            SELECT id FROM document_store_jobs WHERE status = 'processing'
          )
        """
    )
    return cursor.rowcount


def recover_interrupted_documents(
    recover_queued_jobs: bool = True,
    stale_processing_threshold_seconds: Optional[float] = None,
) -> int:
    """Mark documents stuck in an in-flight status as failed.

    Called once at startup. Returns the number of documents recovered.
    Each recovered document gets error="Interrupted by server restart" so
    the UI can surface a clear reason and the user can re-trigger ingestion.

    Also flips jobs left in 'processing' to 'failed' (a job that was actively
    running when the process died cannot be resumed mid-conversion). When
    ``recover_queued_jobs`` is True (the default, used by the in-process
    dispatch mode), jobs left in 'queued' are also flipped to 'failed' so the
    document_store_jobs table doesn't accumulate ghost rows, AND documents
    still at 'queued' (uploaded but never picked up before the crash) are
    flipped to 'failed' so the UI shows a clear retry option instead of a
    permanently stuck 'queued' document.

    When ``recover_queued_jobs`` is False (used in worker-dispatch mode),
    'queued' jobs AND documents are LEFT in place so the ingest-worker can
    pick them up after an API-container restart -- only 'processing' jobs
    (from a worker crash) are marked failed.

    When ``stale_processing_threshold_seconds`` is set, only 'processing' jobs
    whose ``updated_at`` is older than the threshold (relative to now) are
    marked failed. This is used by the worker's periodic stuck-job sweep: a
    job that has been 'processing' for longer than the Docling timeout is
    presumed hung (worker OOM, infinite loop) and marked failed. When None
    (the default, used at startup), all 'processing' jobs are recovered.
    """
    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in _INTERRUPTED_STATUSES)
        job_rows = 0
        if stale_processing_threshold_seconds is not None:
            # Worker periodic sweep: only mark 'processing' jobs whose
            # updated_at is older than the threshold as stale/hung. Also
            # mark the corresponding documents as failed -- but ONLY those
            # whose job is actually stale, not all in-flight documents.
            # max(1, ...) avoids int() truncating sub-second thresholds to 0,
            # which would match all processing jobs regardless of age.
            stale_secs = max(1, int(stale_processing_threshold_seconds))
            stale_doc_ids = conn.execute(
                """
                SELECT DISTINCT document_id
                FROM document_store_jobs
                WHERE status = 'processing'
                  AND updated_at < datetime('now', ? || ' seconds')
                """,
                (f"-{stale_secs}",),
            ).fetchall()
            if stale_doc_ids:
                doc_placeholders = ",".join("?" for _ in stale_doc_ids)
                cursor = conn.execute(
                    f"""
                    UPDATE document_store_documents
                    SET status = 'failed',
                        error = 'Worker timed out (job hung beyond conversion timeout)',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id IN ({doc_placeholders})
                      AND status IN ({placeholders})
                    """,
                    tuple(r[0] for r in stale_doc_ids) + tuple(_INTERRUPTED_STATUSES),
                )
                count = cursor.rowcount
            else:
                count = 0
            job_cursor = conn.execute(
                """
                UPDATE document_store_jobs
                SET status = 'failed',
                    error = 'Worker timed out (job hung beyond conversion timeout)',
                    updated_at = CURRENT_TIMESTAMP
                WHERE status = 'processing'
                  AND updated_at < datetime('now', ? || ' seconds')
                """,
                (f"-{stale_secs}",),
            )
            job_rows = job_cursor.rowcount
        else:
            # Startup recovery: mark ALL documents in interrupted statuses
            # as failed (the process was restarted, so no in-flight job will
            # ever resume). This runs at API startup (in_process mode) and
            # worker startup.
            #
            # In in_process mode (recover_queued_jobs=True) we also flip
            # documents still at 'queued' -- they were uploaded but never
            # picked up by a BackgroundTask before the process died. Without
            # this the job row is marked failed but the document stays
            # 'queued' forever, leaving the UI stuck with no retry option.
            # In worker mode (recover_queued_jobs=False) 'queued' documents
            # are left untouched so the ingest-worker can pick them up after
            # the API-container restart.
            doc_statuses = _INTERRUPTED_STATUSES + (("queued",) if recover_queued_jobs else ())
            doc_placeholders = ",".join("?" for _ in doc_statuses)
            cursor = conn.execute(
                f"""
                UPDATE document_store_documents
                SET status = 'failed',
                    error = 'Interrupted by server restart',
                    updated_at = CURRENT_TIMESTAMP
                WHERE status IN ({doc_placeholders})
                """,
                tuple(doc_statuses),
            )
            count = cursor.rowcount
            if recover_queued_jobs:
                job_cursor = conn.execute(
                    """
                    UPDATE document_store_jobs
                    SET status = 'failed',
                        error = 'Interrupted by server restart',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE status IN ('queued', 'processing')
                    """
                )
            else:
                # Worker startup: all 'processing' jobs are interrupted;
                # 'queued' jobs must survive so the worker can pick them up.
                job_cursor = conn.execute(
                    """
                    UPDATE document_store_jobs
                    SET status = 'failed',
                        error = 'Interrupted by worker restart',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE status = 'processing'
                    """
                )
            job_rows = job_cursor.rowcount
        released_locks = _release_stale_document_locks(conn)
        if count or job_rows or released_locks:
            conn.commit()
        return count
    finally:
        conn.close()
