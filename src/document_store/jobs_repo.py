"""Job record CRUD and atomic job claiming for the ingest worker.

SQLite access for the ``document_store_jobs`` table: creating queued jobs
(with dedup of an already-queued identical action), updating job status,
fetching a job by id, and the atomic ``claim_next_job`` that lets multiple
worker processes safely pull the next queued job without double-claiming.
"""

from __future__ import annotations

import uuid
from typing import Optional

from ..db.database import get_connection
from .models import DocumentJob, JobStatus


def _row_to_job(row) -> DocumentJob:
    return DocumentJob(
        id=row["id"],
        document_id=row["document_id"],
        action=row["action"],
        status=row["status"],
        message=row["message"],
        error=row["error"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def create_job(document_id: str, action: str, message: Optional[str] = None) -> DocumentJob:
    """Create a queued job row for a document.

    If a job with the same (document_id, action) is already ``queued``, return
    that existing job instead of creating a duplicate. This prevents the user
    from spamming restart/delete and accumulating redundant jobs.

    A ``processing`` job is NOT treated as a duplicate -- if the worker crashed
    mid-job, the stuck job is only swept by the periodic stale sweep after
    ``DOCUMENT_DOCLING_TIMEOUT + 60s`` (~31 min). Blocking the user from
    creating a new job during that window would leave them with no recovery
    path except manual DB intervention.
    """
    conn = get_connection()
    try:
        with conn:
            existing = conn.execute(
                "SELECT * FROM document_store_jobs "
                "WHERE document_id = ? AND action = ? AND status = 'queued' "
                "ORDER BY created_at DESC LIMIT 1",
                (document_id, action),
            ).fetchone()
            if existing is not None:
                return _row_to_job(existing)
            job = DocumentJob(
                id=f"job_{uuid.uuid4().hex[:16]}",
                document_id=document_id,
                action=action,
                status="queued",
                message=message,
            )
            conn.execute(
                "INSERT INTO document_store_jobs (id, document_id, action, status, message) VALUES (?, ?, ?, ?, ?)",
                (job.id, job.document_id, job.action, job.status, job.message),
            )
    finally:
        conn.close()
    return job


def update_job(job_id: str, status: JobStatus, message: Optional[str] = None, error: Optional[str] = None) -> None:
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """
                UPDATE document_store_jobs
                SET status = ?, message = ?, error = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, message, error, job_id),
            )
    finally:
        conn.close()


def get_job(job_id: str) -> Optional[DocumentJob]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM document_store_jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            return None
        return _row_to_job(row)
    finally:
        conn.close()


def claim_next_job() -> Optional[DocumentJob]:
    """Atomically claim the next 'queued' job for processing.

    Uses ``UPDATE ... WHERE status = 'queued'`` with a ``rowcount == 1`` check
    so that two workers (e.g. ``docker compose up --scale ingest-worker=2``)
    can never pick up the same job: the SELECT-then-UPDATE window is closed by
    the conditional UPDATE -- only one worker's UPDATE matches.

    Job priority: ``delete`` > ``reindex`` > ``process``. Delete and reindex
    are lightweight operations that should not wait behind slow PDF
    conversions. Within each priority tier, the oldest job (by ``created_at``)
    is claimed first.

    Returns the claimed job (with its original row data) or ``None`` when no
    queued job is available.
    """
    conn = get_connection()
    try:
        with conn:
            row = conn.execute(
                "SELECT j.*, d.processing_job_id AS doc_processing_job_id, d.status AS doc_status "
                "FROM document_store_jobs j "
                "JOIN document_store_documents d ON j.document_id = d.id "
                "WHERE j.status = 'queued' "
                "  AND d.processing_job_id IS NULL "
                "ORDER BY CASE j.action "
                "  WHEN 'delete' THEN 0 "
                "  WHEN 'reindex' THEN 1 "
                "  ELSE 2 "
                "END, j.created_at ASC LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            cursor = conn.execute(
                "UPDATE document_store_jobs SET status = 'processing', "
                "updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'queued'",
                (row["id"],),
            )
            if cursor.rowcount != 1:
                # Another worker claimed it between the SELECT and UPDATE -- skip.
                return None
            return DocumentJob(
                id=row["id"],
                document_id=row["document_id"],
                action=row["action"],
                status="processing",
                message=row["message"],
                error=row["error"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
    finally:
        conn.close()
