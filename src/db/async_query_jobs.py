"""SQLite persistence for async query jobs.

Used by ``AsyncQueryJobManager`` so queued and in-flight jobs survive restarts.
All functions are synchronous and run inside ``asyncio.to_thread`` from the
async manager.

The table is created by migration ``007_async_query_jobs.sql`` at startup via
``run_migrations()``. ``ensure_schema()`` is called once during manager startup
as a safety net for environments that bypass migrations (e.g. tests).
"""

import json
from typing import Any, Dict, List, Optional

from .database import get_connection


def ensure_schema() -> None:
    """Create the table + indexes if missing. Called once per manager start.

    ``CREATE TABLE IF NOT EXISTS`` is a cheap no-op when the migration already
    created the table, so this is safe to call even when migrations ran first.
    """
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS async_query_jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                submitted_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                payload TEXT NOT NULL,
                result TEXT,
                error TEXT,
                expires_at REAL,
                client_request_id TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_async_query_jobs_status "
            "ON async_query_jobs(status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_async_query_jobs_expires_at "
            "ON async_query_jobs(expires_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_async_query_jobs_client_request_id "
            "ON async_query_jobs(client_request_id)"
        )
        conn.commit()
    finally:
        conn.close()


def _loads(value: Optional[str]) -> Any:
    if value is None:
        return None
    return json.loads(value)


def _dumps(value: Any) -> str:
    # default=str protects against any Pydantic dump that left a datetime object,
    # while still serializing the dict structure correctly.
    return json.dumps(value, ensure_ascii=True, default=str)


def _row_to_public(row: Any) -> Dict[str, Any]:
    return {
        "job_id": row["job_id"],
        "status": row["status"],
        "submitted_at": row["submitted_at"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "result": _loads(row["result"]),
        "error": row["error"],
    }


def create_job(
    job_id: str,
    payload: Dict[str, Any],
    submitted_at: str,
    client_request_id: Optional[str] = None,
) -> None:
    """Insert a new queued job."""
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO async_query_jobs
            (job_id, status, submitted_at, payload, client_request_id, expires_at)
            VALUES (?, 'queued', ?, ?, ?, NULL)
            """,
            (job_id, submitted_at, _dumps(payload), client_request_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_job_public(job_id: str) -> Optional[Dict[str, Any]]:
    """Return public job fields (no payload) or None if not found."""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT job_id, status, submitted_at, started_at, completed_at,
                   result, error
            FROM async_query_jobs
            WHERE job_id = ?
            """,
            (job_id,),
        ).fetchone()
        return _row_to_public(row) if row else None
    finally:
        conn.close()


def get_job_with_payload(job_id: str) -> Optional[Dict[str, Any]]:
    """Return full job including payload, used by workers."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM async_query_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        if row is None:
            return None
        return {
            **_row_to_public(row),
            "payload": _loads(row["payload"]),
            "client_request_id": row["client_request_id"],
            "expires_at": row["expires_at"],
        }
    finally:
        conn.close()


def find_active_job_by_client_request_id(
    client_request_id: str,
    now: float,
) -> Optional[Dict[str, Any]]:
    """Return the most recent non-expired job for this idempotency key."""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT job_id, status, submitted_at, started_at, completed_at,
                   result, error
            FROM async_query_jobs
            WHERE client_request_id = ?
              AND (expires_at IS NULL OR expires_at > ?)
            ORDER BY submitted_at DESC
            LIMIT 1
            """,
            (client_request_id, now),
        ).fetchone()
        return _row_to_public(row) if row else None
    finally:
        conn.close()


def count_queued_jobs() -> int:
    """Number of jobs currently waiting to be processed."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM async_query_jobs WHERE status = 'queued'"
        ).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def claim_job(job_id: str, started_at: str) -> bool:
    """Atomically move a queued job to processing. Returns True on success."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            UPDATE async_query_jobs
            SET status = 'processing', started_at = ?
            WHERE job_id = ? AND status = 'queued'
            """,
            (started_at, job_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def complete_job(
    job_id: str,
    result: Dict[str, Any],
    completed_at: str,
    expires_at: float,
) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE async_query_jobs
            SET status = 'completed',
                completed_at = ?,
                result = ?,
                error = NULL,
                expires_at = ?
            WHERE job_id = ?
            """,
            (completed_at, _dumps(result), expires_at, job_id),
        )
        conn.commit()
    finally:
        conn.close()


def fail_job(
    job_id: str,
    error: str,
    completed_at: str,
    expires_at: float,
) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE async_query_jobs
            SET status = 'failed',
                completed_at = ?,
                error = ?,
                result = NULL,
                expires_at = ?
            WHERE job_id = ?
            """,
            (completed_at, error, expires_at, job_id),
        )
        conn.commit()
    finally:
        conn.close()


def mark_interrupted_processing(
    completed_at: str,
    expires_at: float,
) -> int:
    """Mark any left-over processing rows as failed after a restart."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            UPDATE async_query_jobs
            SET status = 'failed',
                completed_at = ?,
                error = 'interrupted by restart',
                result = NULL,
                expires_at = ?
            WHERE status = 'processing' AND result IS NULL
            """,
            (completed_at, expires_at),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def load_queued_job_ids() -> List[str]:
    """Job IDs to re-enqueue on startup."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT job_id FROM async_query_jobs "
            "WHERE status = 'queued' ORDER BY submitted_at"
        ).fetchall()
        return [row["job_id"] for row in rows]
    finally:
        conn.close()


def prune_expired_jobs(now: float) -> int:
    """Delete terminal jobs whose expires_at has passed."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            DELETE FROM async_query_jobs
            WHERE status IN ('completed', 'failed')
              AND expires_at IS NOT NULL
              AND expires_at <= ?
            """,
            (now,),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()
