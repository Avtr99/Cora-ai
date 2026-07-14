"""Shared logging helpers for the document-store ingestion pipeline."""

from __future__ import annotations

from typing import Optional

from loguru import logger


def _log_ingestion_stage(
    scope: str,
    stage: str,
    document_id: str,
    job_id: Optional[str],
    elapsed_seconds: float,
    chunk_count: Optional[int] = None,
) -> None:
    """Emit a safe, structured timing log for an ingestion sub-stage.

    Only metadata (ids, stage name, duration, chunk count) is logged. Document
    content, credentials, and other PII are never included.

    Args:
        scope: Logical scope of the stage, e.g. ``indexer`` or ``job``.
        stage: Short stage identifier for filtering/aggregation.
        document_id: Internal document store ID.
        job_id: Ingestion job ID, if available.
        elapsed_seconds: Wall-clock time spent in the stage.
        chunk_count: Number of chunks processed, when applicable.
    """
    if chunk_count is not None:
        logger.info(
            "Ingestion {scope} stage: stage={stage} document_id={document_id} job_id={job_id} chunk_count={chunk_count} elapsed_seconds={elapsed_seconds:.3f}",
            scope=scope,
            stage=stage,
            document_id=document_id,
            job_id=job_id or "none",
            chunk_count=chunk_count,
            elapsed_seconds=elapsed_seconds,
        )
    else:
        logger.info(
            "Ingestion {scope} stage: stage={stage} document_id={document_id} job_id={job_id} elapsed_seconds={elapsed_seconds:.3f}",
            scope=scope,
            stage=stage,
            document_id=document_id,
            job_id=job_id or "none",
            elapsed_seconds=elapsed_seconds,
        )
