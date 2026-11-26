"""
Async Query Job Manager

Provides queue-backed, SQLite-persistent execution for long-running query requests.
"""

import asyncio
import json
import re
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

from fastapi import HTTPException
from loguru import logger
from tenacity import (
    AsyncRetrying,
    retry,
    retry_if_exception,
    retry_if_exception_type,
    wait_exponential,
)

from ..db import async_query_jobs as job_store
from ..query_processing.fallback_answers import is_error_fallback_result


JobProcessor = Callable[[Dict[str, Any], str, str], Awaitable[Dict[str, Any]]]
MAX_PAYLOAD_BYTES = 32 * 1024
_DEFAULT_INTERNAL_ERROR_MESSAGE = "Internal error processing query"
_QUERY_FALLBACK_ERROR = "The query did not produce an answer."


def _is_sqlite_lock_error(exc: BaseException) -> bool:
    # Extended SQLite result codes keep their primary code in the low byte.
    return isinstance(exc, sqlite3.OperationalError) and (
        getattr(exc, "sqlite_errorcode", 0) & 0xFF
    ) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_error_text(message: str) -> str:
    """Remove high-risk path/id details from user-facing error text."""
    sanitized = message.strip()
    sanitized = re.sub(r"[A-Za-z]:\\[^\s'\"]+", "[path]", sanitized)
    sanitized = re.sub(r"/(?:[^\s/]+/)+[^\s/]+", "[path]", sanitized)
    sanitized = re.sub(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
        "[id]",
        sanitized,
    )
    sanitized = re.sub(r"\b[0-9a-f]{32}\b", "[id]", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()

    if len(sanitized) > 160:
        return f"{sanitized[:157]}..."
    return sanitized


def _format_exception(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        safe_detail = _sanitize_error_text(str(exc.detail or "Request failed"))
        return f"HTTP {exc.status_code}: {safe_detail}"
    return _DEFAULT_INTERNAL_ERROR_MESSAGE


class AsyncQueryJobManager:
    """SQLite-backed queue manager for async query jobs.

    The in-memory asyncio.Queue is used only to signal workers. All state lives
    in SQLite, so queued and in-flight jobs survive restarts and can be resumed.
    """

    def __init__(self, max_queue_size: int = 100, job_ttl_seconds: int = 3600, per_caller_queue_max: int = 20) -> None:
        self._max_queue_size = max_queue_size
        self._job_ttl_seconds = job_ttl_seconds
        self._per_caller_queue_max = per_caller_queue_max
        self._job_callers: Dict[str, str] = {}
        self._retry_tasks: set[asyncio.Task] = set()
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._processor: Optional[JobProcessor] = None
        self._lock = asyncio.Lock()
        self._workers: list[asyncio.Task] = []
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        self._shutdown_event = asyncio.Event()

    def register_processor(self, processor: JobProcessor) -> None:
        """Register async processor used by worker tasks."""
        self._processor = processor

    async def configure(self, max_queue_size: int, job_ttl_seconds: int, per_caller_queue_max: int = 20) -> None:
        """Configure queue and TTL before workers are started."""
        async with self._lock:
            if self._running:
                logger.warning("Async query manager already running; skipping reconfiguration")
                return

            self._max_queue_size = max_queue_size
            self._job_ttl_seconds = job_ttl_seconds
            self._per_caller_queue_max = per_caller_queue_max
            self._job_callers.clear()
            self._queue = asyncio.Queue()

    async def start(self, worker_count: int = 1) -> None:
        """Start background workers and resume any queued jobs from the database."""
        async with self._lock:
            if self._running:
                return

            if self._processor is None:
                raise RuntimeError("Async query processor is not registered")

            self._shutdown_event.clear()
            await self._recover_jobs()
            self._workers = [
                self._spawn_worker(worker_id=i + 1)
                for i in range(max(worker_count, 1))
            ]
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
            self._running = True

        logger.info(
            "Async query job manager started",
            extra={
                "workers": len(self._workers),
                "max_queue_size": self._max_queue_size,
                "job_ttl_seconds": self._job_ttl_seconds,
            },
        )

    def _spawn_worker(self, worker_id: int) -> asyncio.Task:
        """Create a worker task that replaces itself if it dies while running."""
        task = asyncio.create_task(self._worker_loop(worker_id=worker_id))
        task.add_done_callback(lambda t: self._on_worker_done(worker_id, t))
        return task

    def _on_worker_done(self, worker_id: int, task: asyncio.Task) -> None:
        """Respawn a worker that terminated unexpectedly (any cause, not just job failures)."""
        if task.cancelled() or self._shutdown_event.is_set() or not self._running:
            return

        exc = task.exception()
        logger.error(
            f"Async query worker died unexpectedly: worker-{worker_id}: {exc!r}",
        )
        replacement = self._spawn_worker(worker_id)
        self._workers = [replacement if t is task else t for t in self._workers]
        logger.info(f"Respawned async query worker: worker-{worker_id}")

    async def stop(self) -> None:
        """Stop workers and release queue resources."""
        async with self._lock:
            if not self._running:
                return

            self._shutdown_event.set()
            workers = list(self._workers)
            cleanup_task = self._cleanup_task
            self._workers = []
            self._cleanup_task = None
            self._running = False

        for task in (*workers, *self._retry_tasks, cleanup_task):
            if task is not None:
                task.cancel()

        worker_tasks = [t for t in (*workers, cleanup_task) if t is not None]
        if worker_tasks:
            await asyncio.gather(*worker_tasks, return_exceptions=True)

        retry_tasks = list(self._retry_tasks)
        self._retry_tasks.clear()
        for retry_task in retry_tasks:
            retry_task.cancel()
        if retry_tasks:
            await asyncio.gather(*retry_tasks, return_exceptions=True)

        logger.info("Async query job manager stopped")

    async def enqueue(self, payload: Dict[str, Any], user_id: str, caller: Optional[str] = None) -> Dict[str, Any]:
        """Enqueue a new async query job for ``user_id``, or return an existing one by idempotency key.

        ``caller`` identifies the submitting client (e.g. request IP). A per-caller
        bound prevents one caller from holding every queued slot, which matters
        because all callers share the single-owner ``user_id``.
        """
        if not self._running:
            raise RuntimeError("Async query service is not ready")

        validated_payload = self._validate_payload(payload)

        client_request_id: Optional[str] = validated_payload.get("client_request_id")
        caller_key = caller or user_id

        async with self._lock:
            if client_request_id:
                existing = await asyncio.to_thread(
                    job_store.find_active_job_by_client_request_id,
                    user_id,
                    client_request_id,
                    time.time(),
                )
                if existing:
                    existing["queue_depth"] = await self._queue_depth()
                    return self._to_accepted(existing)

            queue_depth = await self._queue_depth()
            if queue_depth >= self._max_queue_size:
                raise asyncio.QueueFull

            caller_queued = sum(key == caller_key for key in self._job_callers.values())
            if caller_queued >= self._per_caller_queue_max:
                raise asyncio.QueueFull

            job_id = uuid.uuid4().hex
            submitted_at = _utc_now_iso()
            await asyncio.to_thread(
                job_store.create_job,
                job_id,
                validated_payload,
                submitted_at,
                user_id,
                client_request_id,
                caller_key,
            )
            self._job_callers[job_id] = caller_key
            self._queue.put_nowait(job_id)

            return {
                "job_id": job_id,
                "status": "queued",
                "submitted_at": submitted_at,
                "queue_depth": queue_depth + 1,
            }

    async def get_job(self, job_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get public job details by ID, scoped to the owning user."""
        return await asyncio.to_thread(job_store.get_job_public, job_id, user_id)

    async def _queue_depth(self) -> int:
        return await asyncio.to_thread(job_store.count_queued_jobs)

    async def _recover_jobs(self) -> None:
        """On startup, mark interrupted processing jobs as failed and re-enqueue queued jobs."""
        completed_at = _utc_now_iso()
        expires_at = time.time() + self._job_ttl_seconds

        interrupted = await asyncio.to_thread(
            job_store.mark_interrupted_processing,
            completed_at,
            expires_at,
        )
        if interrupted:
            logger.warning(f"Marked {interrupted} interrupted processing job(s) as failed")

        self._job_callers.clear()
        queued_jobs = await asyncio.to_thread(job_store.load_queued_jobs)
        if queued_jobs:
            logger.info(f"Resuming {len(queued_jobs)} queued async query job(s)")
            for job in queued_jobs:
                job_id = job["job_id"]
                self._job_callers[job_id] = job["caller"]
                self._queue.put_nowait(job_id)

    async def _worker_loop(self, worker_id: int) -> None:
        """Process jobs sequentially from the queue."""
        logger.info(f"Async query worker started: worker-{worker_id}")
        queue = self._queue

        while not self._shutdown_event.is_set():
            try:
                job_id = await asyncio.wait_for(queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            self._job_callers.pop(job_id, None)

            try:
                try:
                    claimed = await asyncio.to_thread(job_store.claim_job, job_id, _utc_now_iso())
                    if not claimed:
                        queue.task_done()
                        continue

                    job = await asyncio.to_thread(job_store.get_job_with_payload, job_id)
                    if job is None:
                        queue.task_done()
                        continue

                    payload = job["payload"]
                    if not isinstance(payload, dict):
                        raise ValueError("Stored async query payload is not an object")

                    result = self._normalize_result(
                        await self._processor(payload, job_id, job["user_id"])  # type: ignore[misc]
                    )
                except Exception as exc:
                    logger.exception(
                        f"Async query job failed [job_id={job_id}]: {type(exc).__name__}",
                    )
                    result = None
                    error = _format_exception(exc)
                else:
                    error = _QUERY_FALLBACK_ERROR if is_error_fallback_result(result) else None

                try:
                    await self._finish_job(job_id, result=result, error=error)
                except Exception:
                    logger.exception(
                        f"Failed to persist terminal state for async query job [job_id={job_id}]; scheduling retry"
                    )
                    task = asyncio.create_task(
                        self._retry_finish_job(job_id, queue, result=result, error=error)
                    )
                    self._retry_tasks.add(task)
                    task.add_done_callback(self._retry_tasks.discard)
                else:
                    queue.task_done()
            except asyncio.CancelledError:
                break

        logger.info(f"Async query worker stopped: worker-{worker_id}")

    async def _retry_finish_job(
        self,
        job_id: str,
        queue: asyncio.Queue[str],
        *,
        result: Optional[Dict[str, Any]],
        error: Optional[str],
    ) -> None:
        await asyncio.sleep(0.1)
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type(Exception),
            wait=wait_exponential(multiplier=0.1, max=5),
        ):
            if self._shutdown_event.is_set():
                return
            with attempt:
                await self._finish_job(job_id, result=result, error=error)
        queue.task_done()

    @retry(retry=retry_if_exception(_is_sqlite_lock_error), wait=wait_exponential(multiplier=0.1, max=5))
    async def _finish_job(
        self, job_id: str, *, result: Optional[Dict[str, Any]], error: Optional[str]
    ) -> None:
        """Wait out SQLite lock contention without running the query again."""
        await asyncio.to_thread(
            job_store.finish_job,
            job_id,
            _utc_now_iso(),
            time.time() + self._job_ttl_seconds,
            result=result,
            error=error,
        )

    async def _periodic_cleanup(self) -> None:
        """Run expired-job cleanup every minute while the manager is active.

        ponytail: Workers already clean up after each job; this catches the
        quiet-idle case where no queries arrive and completed jobs would linger.
        """
        while not self._shutdown_event.is_set():
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(), timeout=60.0
                )
            except asyncio.TimeoutError:
                await self._cleanup_expired_jobs()
            except asyncio.CancelledError:
                break

    @staticmethod
    def _validate_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Async query payload must be an object")

        try:
            serialized_payload = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
        except (TypeError, ValueError) as exc:
            raise ValueError("Async query payload must be JSON serializable") from exc

        payload_size = len(serialized_payload.encode("utf-8"))
        if payload_size > MAX_PAYLOAD_BYTES:
            raise ValueError(
                f"Async query payload exceeds {MAX_PAYLOAD_BYTES} bytes limit"
            )

        return json.loads(serialized_payload)

    @staticmethod
    def _normalize_result(result: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(result, dict):
            raise ValueError("Async query result must be an object")
        return json.loads(
            json.dumps(result, ensure_ascii=True, allow_nan=False, default=str)
        )

    async def _cleanup_expired_jobs(self) -> None:
        """Delete terminal jobs whose TTL has expired.

        ponytail: we do not keep tombstones for 410 Gone responses; an expired
        and pruned job is indistinguishable from a never-created one (404). This
        matches the original in-memory behavior and avoids keeping extra state.
        """
        try:
            pruned = await asyncio.to_thread(job_store.prune_expired_jobs, time.time())
            if pruned:
                logger.debug(f"Cleaned up {pruned} expired async query jobs")
        except Exception:
            logger.exception("Failed to prune expired async query jobs")

    @staticmethod
    def _to_accepted(job: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "job_id": job["job_id"],
            "status": job["status"],
            "submitted_at": job["submitted_at"],
            "queue_depth": job.get("queue_depth", 0),
        }


_async_query_job_manager = AsyncQueryJobManager()


def get_async_query_job_manager() -> AsyncQueryJobManager:
    return _async_query_job_manager
