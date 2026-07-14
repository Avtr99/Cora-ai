from __future__ import annotations

from typing import Optional

import re
import time
from pathlib import Path

from loguru import logger

try:
    from docling.exceptions import ConversionError as _DoclingConversionError
except Exception:  # pragma: no cover - docling may not be installed in all environments
    _DoclingConversionError = None

from ..config import get_settings
from .converter import convert_document, write_converted_markdown
from .indexer import delete_document_chunks, index_document
from .ingestion_pool import _get_ingestion_sem
from .logging_utils import _log_ingestion_stage
from .models import DocumentRecord
from .storage import (
    get_document,
    get_document_including_deleted,
    remove_document_files,
    update_document,
    update_job,
)

# Process-level flag: once a Docling standard conversion has completed in this
# process, model weights are cached in memory and (usually) on disk, so we stop
# emitting the "downloading models" notice for subsequent conversions.
_docling_models_warmed = False


def _docling_models_cached() -> Optional[bool]:
    """Heuristic: are Docling model artifacts already on disk?

    Returns True if ``DOCLING_ARTIFACTS_PATH`` is set and non-empty, False if it is
    set but missing/empty, and None when the path is unset (unknown — rely on the
    process-level warmed flag instead).
    """
    artifacts = get_settings().DOCLING_ARTIFACTS_PATH
    if not artifacts:
        return None
    p = Path(artifacts)
    return p.exists() and any(p.iterdir())


def _maybe_emit_docling_download_notice(job_id: str, record: DocumentRecord) -> None:
    """Emit a 'downloading models' job status update before the first standard PDF
    conversion when models aren't yet cached, so the user sees a download is
    happening instead of a frozen converter."""
    global _docling_models_warmed
    if record.conversion_mode != "standard" or record.extension.lower() != ".pdf":
        return
    if _docling_models_warmed:
        return
    cached = _docling_models_cached()
    if cached is True:
        _docling_models_warmed = True
        return
    update_job(
        job_id,
        "processing",
        "Downloading Docling models (first run only, ~670MB). This may take several minutes.",
    )


def _refresh_record(document_id: str, job_id: str) -> Optional[DocumentRecord]:
    """Reload a document record; mark the job failed if the document is gone."""
    record = get_document(document_id)
    if record is None:
        # Check if the record was already deleted (e.g. duplicate delete job).
        existing = get_document_including_deleted(document_id)
        if existing is not None and existing.status == "deleted":
            update_job(job_id, "completed", message="Document already deleted")
        else:
            update_job(job_id, "failed", error="Document not found")
    return record


def _extract_docling_error_detail(exc_str: str) -> str:
    """Return the user-relevant portion of a Docling ConversionError message.

    Docling wraps failures as:
      "Conversion failed for: <file> with status: <status>. Errors: <details>"
    The useful part for the user is after ``Errors:``.
    """
    if "Errors:" in exc_str:
        return exc_str.split("Errors:", 1)[1].strip()
    return exc_str


def _classify_docling_conversion_error(exc: Exception) -> str:
    """User-friendly, actionable message for a Docling ConversionError.

    The frontend labels the modes as ``Standard`` and ``LLM API``, so error text
    uses those exact names. Where possible we extract concrete numbers from the
    Docling message so the user sees *why* instead of a generic failure.
    """
    exc_str = str(exc)
    detail = _extract_docling_error_detail(exc_str)
    low = detail.lower()

    # File size limit (defense in depth behind the upload limit)
    if "max_file_size" in low:
        match = re.search(
            r"size (\d+).*?exceeds.*?max_file_size.*?(\d+)",
            low,
        )
        if match:
            size, limit = match.groups()
            return (
                f"This PDF file is too large ({int(size):,} bytes; limit is "
                f"{int(limit):,} bytes) for Standard mode. Reduce the file size "
                "or increase the limit in Settings (DOCUMENT_DOCLING_MAX_FILE_BYTES)."
            )
        return (
            "This PDF file is too large for Standard mode. Reduce the file size or "
            "increase the limit in Settings (DOCUMENT_DOCLING_MAX_FILE_BYTES)."
        )

    # Timeout
    if "timeout" in low:
        return (
            "Standard mode took too long to convert this PDF. Try a smaller PDF, "
            "reduce the page count, increase DOCUMENT_DOCLING_TIMEOUT, or switch to LLM API mode."
        )

    # Backend parse failure (corrupted, password-protected, unsupported)
    if "could not parse the input" in low:
        return (
            "Standard mode couldn't read this PDF. It may be corrupted, "
            "password-protected, or in an unsupported format. Try re-saving it as a "
            "new PDF or switch to LLM API mode."
        )

    # Source unavailable (file moved/deleted)
    if "not found or cannot be opened" in low:
        return (
            "The PDF file couldn't be opened. It may have been moved or deleted. "
            "Please re-upload it."
        )

    # Generic fallback: surface the detail, not the full wrapper sentence.
    return (
        f"Standard mode couldn't convert this PDF: {detail}. "
        "Check the server logs or switch to LLM API mode."
    )


def _classify_conversion_error(exc: Exception, conversion_mode: str = "standard") -> str:
    """Translate a raw exception into a user-actionable error message.

    The raw exception is still logged via logger.exception; this function only
    controls what the user sees in the document's error field and the UI.

    ``conversion_mode`` lets us avoid telling a user to "try Standard mode" when
    they are already in Standard mode.
    """
    exc_str = str(exc)
    exc_type = type(exc).__name__
    is_standard = conversion_mode == "standard"
    is_llm_api = conversion_mode == "llm_api"

    # MemoryError — the host ran out of RAM during conversion
    if isinstance(exc, MemoryError):
        return (
            "Server ran out of memory while converting this PDF. "
            "Try a smaller file, lower DOCUMENT_DOCLING_TIMEOUT, "
            "or use llm_api mode for large/scanned documents."
        )

    # ImportError — Docling (standard) or PyMuPDF (llm_api rendering) missing/broken
    if isinstance(exc, ImportError):
        low = exc_str.lower()
        if "docling" in low or "rapidocr" in low or "onnxtr" in low or "tesserocr" in low:
            return "Docling standard parsing dependencies are missing. Reinstall with `pip install -r requirements.txt`."
        if "fitz" in low or "pymupdf" in low:
            return "PyMuPDF is missing. Server is missing dependencies for PDF conversion. Reinstall with `pip install -r requirements.txt`."
        return "Server is missing dependencies for this conversion mode. Reinstall with `pip install -r requirements.txt`."

    # ValueError — already user-friendly messages from the converter (e.g.
    # PARTIAL_SUCCESS timeout handling in _convert_pdf_with_docling_standard).
    if isinstance(exc, ValueError):
        return exc_str

    # httpx errors — the llm_api path makes direct HTTP calls to the AI provider
    try:
        import httpx

        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code if exc.response is not None else None
            if status in (401, 403):
                return "API key is invalid or expired. Update it in Settings and try again."
            if status == 429:
                return "Rate limited by the AI provider. Wait a minute and try again."
            if status is not None and 500 <= status < 600:
                return f"The AI provider returned a server error (HTTP {status}). Try again in a few minutes."
            return f"The AI provider returned an error (HTTP {status}). Check the server logs for details."

        if isinstance(exc, httpx.TimeoutException):
            if is_standard:
                return "Conversion timed out. Try a smaller PDF or use llm_api mode."
            return "Conversion timed out. Try a smaller PDF or use Standard mode instead."

        if isinstance(exc, (httpx.ConnectError, httpx.NetworkError)):
            return "Could not reach the AI provider. Check your internet connection and try again."
    except ImportError:
        pass  # httpx not installed — fall through to generic handling

    # PyMuPDF errors — corrupted, empty, or password-protected PDFs
    try:
        import fitz

        if isinstance(exc, fitz.EmptyFileError):
            return "This PDF file is empty. Check the file and re-upload."
        if isinstance(exc, fitz.FileDataError):
            return "This PDF could not be parsed. It may be corrupted or password-protected. Try re-saving it as a new PDF."
    except ImportError:
        pass

    # Docling ConversionError — surface the actual message so the user sees the
    # real reason (file size, backend failure, timeout, etc.) instead of a
    # generic "try Standard mode" when already in Standard mode.
    if _DoclingConversionError is not None and isinstance(exc, _DoclingConversionError):
        return _classify_docling_conversion_error(exc)

    # Fallback: include the exception type so the user has something to grep
    # the logs with, but don't suggest the mode they're already using.
    if is_standard:
        return f"Conversion failed ({exc_type}). Check the server logs."
    if is_llm_api:
        return f"Conversion failed ({exc_type}). Check the server logs or try Standard mode."
    return f"Conversion failed ({exc_type}). Check the server logs."


async def process_document_job(document_id: str, job_id: str) -> None:
    async with _get_ingestion_sem():
        await _process_document_job_inner(document_id, job_id)


async def _process_document_job_inner(document_id: str, job_id: str) -> None:
    global _docling_models_warmed
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
        _docling_models_warmed = True

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
        start = time.perf_counter()
        chunk_count = await index_document(record, job_id=job_id)
        _log_ingestion_stage("job", "indexing", document_id, job_id, time.perf_counter() - start, chunk_count)
        update_job(job_id, "completed", f"Ready to use. {chunk_count} text sections added.")
    except Exception as exc:
        logger.exception("Document processing failed for %s", document_id)
        user_error = _classify_conversion_error(exc, record.conversion_mode if record else "standard")
        update_document(document_id, status="failed", error=user_error)
        update_job(job_id, "failed", error=user_error)


async def reindex_document_job(document_id: str, job_id: str) -> None:
    async with _get_ingestion_sem():
        await _reindex_document_job_inner(document_id, job_id)


async def _reindex_document_job_inner(document_id: str, job_id: str) -> None:
    global _docling_models_warmed
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
            _docling_models_warmed = True

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
        logger.exception("Document re-index failed for %s", document_id)
        user_error = _classify_conversion_error(exc, record.conversion_mode if record else "standard")
        update_document(document_id, status="failed", error=user_error)
        update_job(job_id, "failed", error=user_error)


async def delete_document_job(document_id: str, job_id: str) -> None:
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
            logger.warning("Could not mark document %s as deleting: %s", document_id, exc)

    # Always run Qdrant cleanup — it's idempotent (deleting non-existent
    # points is a no-op) and is the only way to purge orphaned chunks left
    # behind by a previous failed delete.
    qdrant_error = None
    try:
        await delete_document_chunks(document_id)
    except Exception as exc:
        logger.exception("Vector store deletion failed for %s", document_id)
        qdrant_error = str(exc)

    try:
        remove_document_files(record)
    except Exception:
        logger.exception("Local file deletion failed for %s", document_id)

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
        logger.exception("Could not mark document %s as deleted", document_id)
        update_job(job_id, "failed", error=str(exc))
