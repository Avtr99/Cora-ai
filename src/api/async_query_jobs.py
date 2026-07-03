"""
Async Query Job Manager

Provides queue-backed execution for long-running query requests.
"""

import asyncio
import json
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

from fastapi import HTTPException
from loguru import logger


JobProcessor = Callable[[Dict[str, Any], str], Awaitable[Dict[str, Any]]]
_TERMINAL_STATUSES = {"completed", "failed"}
MAX_PAYLOAD_BYTES = 32 * 1024
_DEFAULT_INTERNAL_ERROR_MESSAGE = "Internal error processing query"


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

    if str(exc):
        fallback_message = _sanitize_error_text(str(exc))
        if fallback_message and fallback_message.lower() not in {"none", "null"}:
            return _DEFAULT_INTERNAL_ERROR_MESSAGE

    return _DEFAULT_INTERNAL_ERROR_MESSAGE


class AsyncQueryJobManager:
    """In-memory queue-backed manager for async query jobs."""

    def __init__(self, max_queue_size: int = 100, job_ttl_seconds: int = 3600) -> None:
        self._max_queue_size = max_queue_size
        self._job_ttl_seconds = job_ttl_seconds
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=max_queue_size)
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._processor: Optional[JobProcessor] = None
        self._lock = asyncio.Lock()
        self._workers: list[asyncio.Task] = []
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        self._shutdown_event = asyncio.Event()

    def register_processor(self, processor: JobProcessor) -> None:
        """Register async processor used by worker tasks."""
        self._processor = processor

    async def configure(self, max_queue_size: int, job_ttl_seconds: int) -> None:
        """Configure queue and TTL before workers are started."""
        async with self._lock:
            if self._running:
                logger.warning("Async query manager already running; skipping reconfiguration")
                return

            self._max_queue_size = max_queue_size
            self._job_ttl_seconds = job_ttl_seconds
            self._queue = asyncio.Queue(maxsize=max_queue_size)

    async def start(self, worker_count: int = 1) -> None:
        """Start background workers."""
        async with self._lock:
            if self._running:
                return

            if self._processor is None:
                raise RuntimeError("Async query processor is not registered")

            self._shutdown_event.clear()
            self._workers = [
                asyncio.create_task(self._worker_loop(worker_id=i + 1))
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

        for worker in workers:
            worker.cancel()

        if cleanup_task is not None:
            cleanup_task.cancel()

        if workers or cleanup_task is not None:
            await asyncio.gather(*workers, cleanup_task, return_exceptions=True)

        logger.info("Async query job manager stopped")

    async def enqueue(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Enqueue a new async query job."""
        if not self._running:
            raise RuntimeError("Async query service is not ready")

        validated_payload = self._validate_payload(payload)

        await self._cleanup_expired_jobs()

        async with self._lock:
            if self._queue.full():
                raise asyncio.QueueFull

            job_id = uuid.uuid4().hex
            submitted_at = _utc_now_iso()
            self._jobs[job_id] = {
                "job_id": job_id,
                "status": "queued",
                "submitted_at": submitted_at,
                "started_at": None,
                "completed_at": None,
                "result": None,
                "error": None,
                "payload": validated_payload,
                "expires_at_unix": None,
            }
            self._queue.put_nowait(job_id)
            queue_depth = self._queue.qsize()

        return {
            "job_id": job_id,
            "status": "queued",
            "submitted_at": submitted_at,
            "queue_depth": queue_depth,
        }

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get public job details by ID."""
        await self._cleanup_expired_jobs()

        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None

            return self._to_public_job(job)

    async def _worker_loop(self, worker_id: int) -> None:
        """Process jobs sequentially from the queue."""
        logger.info(f"Async query worker started: worker-{worker_id}")

        while not self._shutdown_event.is_set():
            job_id: Optional[str] = None
            try:
                job_id = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            payload: Optional[Dict[str, Any]] = None
            try:
                async with self._lock:
                    job = self._jobs.get(job_id)
                    if job is None:
                        continue

                    job["status"] = "processing"
                    job["started_at"] = _utc_now_iso()
                    payload = dict(job.get("payload", {}))

                if payload is None:
                    continue

                result = await self._processor(payload, job_id)  # type: ignore[misc]

                async with self._lock:
                    job = self._jobs.get(job_id)
                    if job is not None:
                        job["status"] = "completed"
                        job["completed_at"] = _utc_now_iso()
                        job["result"] = result
                        job["error"] = None
                        job["expires_at_unix"] = time.time() + self._job_ttl_seconds

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception(
                    f"Async query job failed [job_id={job_id}]: {type(exc).__name__}",
                )
                async with self._lock:
                    job = self._jobs.get(job_id)
                    if job is not None:
                        job["status"] = "failed"
                        job["completed_at"] = _utc_now_iso()
                        job["error"] = _format_exception(exc)
                        job["result"] = None
                        job["expires_at_unix"] = time.time() + self._job_ttl_seconds
            finally:
                if job_id is not None:
                    self._queue.task_done()
                await self._cleanup_expired_jobs()

        logger.info(f"Async query worker stopped: worker-{worker_id}")

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

    async def _cleanup_expired_jobs(self) -> None:
        now = time.time()
        async with self._lock:
            expired_job_ids = [
                job_id
                for job_id, job in self._jobs.items()
                if job.get("status") in _TERMINAL_STATUSES
                and isinstance(job.get("expires_at_unix"), (int, float))
                and job["expires_at_unix"] <= now
            ]

            for job_id in expired_job_ids:
                self._jobs.pop(job_id, None)

            if expired_job_ids:
                logger.debug(f"Cleaned up {len(expired_job_ids)} expired async query jobs")

    @staticmethod
    def _to_public_job(job: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "job_id": job.get("job_id"),
            "status": job.get("status"),
            "submitted_at": job.get("submitted_at"),
            "started_at": job.get("started_at"),
            "completed_at": job.get("completed_at"),
            "result": job.get("result"),
            "error": job.get("error"),
        }


_async_query_job_manager = AsyncQueryJobManager()


def get_async_query_job_manager() -> AsyncQueryJobManager:
    return _async_query_job_manager
