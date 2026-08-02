"""Job dispatch: route ingestion jobs to in-process BackgroundTasks or the worker queue.

``schedule_ingestion_job`` is the integration point between the HTTP route
handler and the job execution path. In ``in_process`` mode it schedules the
job via FastAPI BackgroundTasks; in ``worker`` mode it does nothing (the job
row was already inserted as ``queued`` and a separate ingest-worker container
polls the table). Delete jobs always run in-process regardless of dispatch
mode -- they are lightweight and should not wait behind multi-minute Docling
conversions.
"""

from __future__ import annotations

from typing import Awaitable, Callable

from fastapi import BackgroundTasks, HTTPException
from loguru import logger

from ..config import get_settings
from .converter import _PDF_EXTENSIONS, get_conversion_capabilities
from .handlers import delete_document_job, process_document_job
from .storage import get_document

# Type alias: an async job handler taking (document_id, job_id).
JobHandler = Callable[[str, str], Awaitable[None]]


def raise_if_conversion_unavailable(conversion_mode: str, extension: str) -> None:
    """Fail fast with 503 if a standard-mode PDF is requested but Docling is unavailable.

    This guards the query-only container misconfiguration (``INSTALL_INGESTION=false``
    + ``INGESTION_DISPATCH=in_process``), where standard PDF conversion would otherwise
    fail with an ``ImportError`` inside a background task. Text/CSV/JSON files do not
    need Docling, so they are allowed.
    """
    if (
        conversion_mode == "standard"
        and extension.lower() in _PDF_EXTENSIONS
        and not get_conversion_capabilities()["standard"]["available"]
    ):
        raise HTTPException(
            status_code=503,
            detail=(
                "Standard PDF conversion is not available in this container. "
                "Set INGESTION_DISPATCH=worker or install the ingestion dependencies."
            ),
        )


def schedule_ingestion_job(
    background_tasks: BackgroundTasks,
    job_fn: JobHandler,
    document_id: str,
    job_id: str,
) -> None:
    """Dispatch an ingestion job according to the configured dispatch mode.

    - ``in_process``: schedule ``job_fn`` via FastAPI BackgroundTasks so the
      API process runs the converter/indexer itself. A 503 is raised if a
      ``standard``-mode PDF conversion is requested but the container does not
      have the ingestion stack installed (the query-only image
      misconfiguration).
    - ``worker``: do nothing here — the job row was already inserted as
      'queued' by the route, and a separate ingest-worker process polls the
      job table and runs the heavy parsing. See
      ``src/document_store/worker.py``.
    """
    # Delete jobs always run in-process, regardless of dispatch mode. Delete
    # only needs Qdrant + filesystem + SQLite — all available in the API
    # container. Routing it through the worker queue would make a 2-second
    # operation wait behind multi-minute Docling conversions.
    if job_fn is delete_document_job:
        background_tasks.add_task(job_fn, document_id, job_id)
        return

    dispatch_mode = getattr(get_settings(), "INGESTION_DISPATCH", "in_process")
    if dispatch_mode == "worker":
        # The job row is already 'queued'; the worker picks it up.
        logger.debug(
            "Worker dispatch: job {} queued for ingest-worker (doc={})",
            job_id, document_id,
        )
        return

    # Defense in depth: if a direct caller (e.g. a test or script) tries to
    # schedule a process job that this container cannot handle, fail fast.
    if job_fn is process_document_job:
        record = get_document(document_id)
        if record is not None:
            raise_if_conversion_unavailable(record.conversion_mode, record.extension)

    background_tasks.add_task(job_fn, document_id, job_id)
