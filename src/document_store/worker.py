"""Ingestion worker entrypoint.

Runs as a separate process/container from the API. Polls the
``document_store_jobs`` SQLite table for ``queued`` jobs, atomically claims
them, and runs up to ``DOCUMENT_INGESTION_CONCURRENCY`` converter/indexer
jobs concurrently so CPU/RAM-heavy PDF/OCR parsing does not stall query
latency on the API container.

Run with::

    python -m src.document_store.worker

The worker shares the same ``./data`` volume (SQLite DB + document files) and
Qdrant instance as the API. Only the worker writes ingestion job rows during
processing; the API only inserts new ``queued`` rows and reads status.

Reliability:
  - On startup, jobs left ``processing`` by a previous worker crash are marked
    ``failed`` (a job interrupted mid-conversion cannot be resumed).
    ``queued`` jobs are preserved so they are picked up after a restart.
  - The atomic claim (``UPDATE ... WHERE status = 'queued'`` with a
    ``rowcount == 1`` check) prevents two workers from picking up the same
    job when ``--scale ingest-worker=N`` is used.
  - A heartbeat is written to ``app_settings`` every ~10s by a background
    task so the API can detect when no worker is running and warn the user,
    even while the worker is busy with a long document. Stuck ``processing``
    jobs whose heartbeat is older than the Docling timeout are marked failed
    on the next worker startup.
"""

from __future__ import annotations

import asyncio
import signal
import time
from typing import Optional

from loguru import logger

from ..config import get_settings
from ..db.app_settings import save_app_setting
from ..db.database import run_migrations
from .jobs import delete_document_job, process_document_job, reindex_document_job
from .models import DocumentJob
from .storage import claim_next_job, ensure_document_store_tables, recover_interrupted_documents, update_job

# Maps a job action to its async handler (document_id, job_id) -> None.
_JOB_HANDLERS = {
    "process": process_document_job,
    "reindex": reindex_document_job,
    "delete": delete_document_job,
}

# Key in app_settings holding the Unix timestamp of the worker's last heartbeat.
_WORKER_HEARTBEAT_KEY = "ingest_worker_heartbeat"


def is_worker_alive() -> bool:
    """Check if the ingest-worker is running based on its heartbeat.

    Returns True if the worker has written a heartbeat to ``app_settings``
    within the last ``INGEST_WORKER_STALE_SECONDS`` seconds. Returns False if
    no heartbeat exists or it is stale (worker not running / crashed).

    Called by the API container to warn users when uploads will not be
    processed.
    """
    from ..db.app_settings import get_app_setting

    try:
        raw = get_app_setting(_WORKER_HEARTBEAT_KEY)
        if raw is None:
            return False
        heartbeat_ts = float(raw)
        stale_seconds = float(get_settings().INGEST_WORKER_STALE_SECONDS)
        return (time.time() - heartbeat_ts) < stale_seconds
    except Exception:
        return False


def _write_heartbeat() -> None:
    """Write the current Unix timestamp to app_settings as a heartbeat."""
    try:
        save_app_setting(_WORKER_HEARTBEAT_KEY, str(time.time()))
    except Exception as e:
        logger.warning("Could not write worker heartbeat: %s", e)


async def _heartbeat_loop(stop_event: asyncio.Event) -> None:
    """Write a heartbeat at the configured interval until stop is set.

    Keeps ``is_worker_alive()`` true while the worker is busy with long-running
    documents, since the main loop may be blocked on conversion/indexing.
    """
    interval = float(get_settings().INGEST_WORKER_HEARTBEAT_INTERVAL_SECONDS)
    while not stop_event.is_set():
        await asyncio.to_thread(_write_heartbeat)
        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=interval,
            )
        except asyncio.TimeoutError:
            pass


async def _process_one(job: DocumentJob) -> None:
    """Run a single claimed job through its handler.

    The handler acquires a SQLite-level document lock, so the worker can run
    jobs for different documents concurrently while the database guarantees
    no two workers (or two in-process BackgroundTasks) mutate the same
    document at the same time. If a job for a locked document is claimed
    (rare, because ``claim_next_job`` filters them out), the handler
    re-queues it and exits.
    """
    handler = _JOB_HANDLERS.get(job.action)
    if handler is None:
        logger.error(
            "Unknown job action {!r} for job {} (doc={}) — marking failed",
            job.action, job.id, job.document_id,
        )
        update_job(job.id, "failed", error=f"Unknown job action: {job.action}")
        return
    logger.info(
        "Worker picked up job {} (action={}, doc={})",
        job.id, job.action, job.document_id,
    )
    await handler(job.document_id, job.id)


async def _finalize_task(task: asyncio.Task) -> None:
    """Await a worker task and log any unhandled exception."""
    if task.cancelled():
        return
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception("Worker task failed")


async def run_worker(stop_event: Optional[asyncio.Event] = None) -> None:
    """Main worker loop: poll for queued jobs and process up to
    ``DOCUMENT_INGESTION_CONCURRENCY`` of them concurrently.

    A background heartbeat task writes to ``app_settings`` every ~10s so the
    API can detect when no worker is running, even while a long document is
    being converted/indexed. Periodically sweeps for stuck ``processing`` jobs
    whose updated_at is older than the Docling conversion timeout and marks
    them failed.

    Args:
        stop_event: When set, the loop drains any running tasks and exits.
            If None, the loop runs until the process is cancelled (SIGINT/SIGTERM).
    """
    settings = get_settings()
    poll_interval = float(settings.INGEST_WORKER_POLL_INTERVAL_SECONDS)
    # Stuck-job threshold: a 'processing' job older than this (relative to its
    # updated_at) is presumed hung. The Docling per-document timeout plus a
    # configurable grace period.
    stale_threshold = (
        float(settings.DOCUMENT_DOCLING_TIMEOUT)
        + float(settings.INGEST_WORKER_STALE_GRACE_SECONDS)
    )
    stale_sweep_every = max(
        1, int(settings.INGEST_WORKER_STALE_SWEEP_EVERY_N_POLLS)
    )
    concurrency = max(1, int(settings.DOCUMENT_INGESTION_CONCURRENCY))
    stop = stop_event or asyncio.Event()
    poll_count = 0
    running: set[asyncio.Task] = set()
    logger.info(
        "Ingestion worker started (concurrency={}, poll interval={}s, stale threshold={}s)",
        concurrency, poll_interval, stale_threshold,
    )

    heartbeat_task = asyncio.create_task(_heartbeat_loop(stop))
    try:
        while not stop.is_set():
            try:
                # Periodic stuck-job sweep — mark 'processing' jobs whose
                # updated_at is older than the conversion timeout as failed.
                poll_count += 1
                if poll_count % stale_sweep_every == 0:
                    recovered = await asyncio.to_thread(
                        recover_interrupted_documents,
                        recover_queued_jobs=False,
                        stale_processing_threshold_seconds=stale_threshold,
                    )
                    if recovered:
                        logger.warning(
                            "Stuck-job sweep: marked {} hung document(s) as failed",
                            recovered,
                        )

                # Fill worker slots up to the configured concurrency. Each job
                # runs in its own task. The handlers' ingestion semaphore
                # (_get_ingestion_sem in jobs.py) is a backstop for in_process
                # BackgroundTasks and is redundant in worker mode — the worker
                # loop already enforces the same cap via len(running) < concurrency.
                # It is harmless (the semaphore count equals the worker's
                # concurrency, so it never blocks) and removing it would require
                # dispatch-mode-aware conditional logic in the shared job handlers,
                # adding complexity for zero benefit.
                while len(running) < concurrency and not stop.is_set():
                    job = await asyncio.to_thread(claim_next_job)
                    if job is None:
                        break
                    task = asyncio.create_task(_process_one(job))
                    running.add(task)

                if not running:
                    try:
                        await asyncio.wait_for(stop.wait(), timeout=poll_interval)
                    except asyncio.TimeoutError:
                        pass
                    continue

                # Wait for at least one slot to free up, a stop signal, or the
                # poll interval to re-check the queue.
                done, running = await asyncio.wait(
                    running,
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=poll_interval,
                )
                for task in done:
                    await _finalize_task(task)
            except asyncio.CancelledError:
                logger.info("Ingestion worker cancelled — exiting")
                raise
            except Exception:
                logger.exception("Worker loop error — continuing after backoff")
                try:
                    await asyncio.wait_for(stop.wait(), timeout=poll_interval)
                except asyncio.TimeoutError:
                    pass
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        if running:
            await asyncio.gather(
                *(_finalize_task(t) for t in running), return_exceptions=True
            )
        logger.info("Ingestion worker stopped")


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    """Translate SIGINT/SIGTERM into a clean stop_event set.

    Must be called from within a running event loop (e.g. inside
    ``run_worker``) so ``asyncio.get_running_loop()`` resolves.
    """
    loop = asyncio.get_running_loop()

    def _stop(*_args) -> None:
        logger.info("Received shutdown signal — draining worker loop")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except (NotImplementedError, RuntimeError):
            # add_signal_handler is not available on Windows / some loops.
            signal.signal(sig, lambda *_a: _stop())


async def _run_with_signals() -> None:
    """Install signal handlers inside the running loop, then run the worker."""
    stop_event = asyncio.Event()
    _install_signal_handlers(stop_event)
    await run_worker(stop_event=stop_event)


def main() -> None:
    """Worker process entrypoint: init DB, recover interrupted jobs, run loop."""
    # Ensure schema exists (the API normally does this, but the worker may
    # start first or against a fresh volume).
    run_migrations()
    ensure_document_store_tables()

    # Recover jobs left 'processing' by a previous worker crash. Preserve
    # 'queued' jobs so they are picked up after a restart.
    recovered = recover_interrupted_documents(recover_queued_jobs=False)
    if recovered:
        logger.warning(
            "Recovered {} interrupted document(s) from a previous worker run",
            recovered,
        )

    asyncio.run(_run_with_signals())


if __name__ == "__main__":
    main()
