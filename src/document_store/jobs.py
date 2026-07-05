from __future__ import annotations

from pathlib import Path

from loguru import logger

from ..config import get_settings
from .converter import convert_document, write_converted_markdown
from .indexer import delete_document_chunks, index_document
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


def _docling_models_cached() -> bool | None:
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


def _refresh_record(document_id: str, job_id: str) -> DocumentRecord | None:
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


def _classify_conversion_error(exc: Exception) -> str:
    """Translate a raw exception into a user-actionable error message.

    The raw exception is still logged via logger.exception; this function only
    controls what the user sees in the document's error field and the UI.
    """
    exc_str = str(exc)
    exc_type = type(exc).__name__

    # MemoryError — the host ran out of RAM during conversion
    if isinstance(exc, MemoryError):
        return (
            "Server ran out of memory while converting this PDF. "
            "Try a smaller file, reduce DOCUMENT_DOCLING_MAX_PAGES, "
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

    # ValueError — already user-friendly messages from the converter
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

    # Fallback: include the exception type so the user has something to grep
    # the logs with, but don't dump a raw traceback fragment.
    return f"Conversion failed ({exc_type}). Check the server logs or try Standard mode."


async def process_document_job(document_id: str, job_id: str) -> None:
    global _docling_models_warmed
    update_job(job_id, "processing", "Reading document")
    record = _refresh_record(document_id, job_id)
    if record is None:
        return
    try:
        update_document(document_id, status="reading", error=None)
        _maybe_emit_docling_download_notice(job_id, record)
        result = await convert_document(record)
        _docling_models_warmed = True
        record = _refresh_record(document_id, job_id)
        if record is None:
            return
        write_converted_markdown(record, result)
        # Persist the VCM metadata extracted during conversion so the indexer
        # and RAG pipeline read from a single source of truth.
        meta = result.metadata
        record = update_document(
            document_id,
            title=meta.get("title"),
            registry=meta.get("registry"),
            publisher=meta.get("publisher"),
            document_id=meta.get("document_id"),
            version_number=meta.get("version_number"),
        )
        update_job(job_id, "processing", "Adding document to Cora")
        chunk_count = await index_document(record)
        update_job(job_id, "completed", f"Ready to use. {chunk_count} text sections added.")
    except Exception as exc:
        logger.exception("Document processing failed for %s", document_id)
        user_error = _classify_conversion_error(exc)
        update_document(document_id, status="failed", error=user_error)
        update_job(job_id, "failed", error=user_error)


async def reindex_document_job(document_id: str, job_id: str) -> None:
    global _docling_models_warmed
    update_job(job_id, "processing", "Refreshing document for Cora")
    record = _refresh_record(document_id, job_id)
    if record is None:
        return
    try:
        if not record.converted_path or not Path(record.converted_path).exists():
            _maybe_emit_docling_download_notice(job_id, record)
            result = await convert_document(record)
            _docling_models_warmed = True
            record = _refresh_record(document_id, job_id)
            if record is None:
                return
            write_converted_markdown(record, result)
            # Persist freshly extracted VCM metadata.
            meta = result.metadata
            record = update_document(
                document_id,
                title=meta.get("title"),
                registry=meta.get("registry"),
                publisher=meta.get("publisher"),
                document_id=meta.get("document_id"),
                version_number=meta.get("version_number"),
            )
        else:
            # Even on reindex without reconversion, re-read metadata from the
            # record so the indexer gets the persisted values.
            record = _refresh_record(document_id, job_id)
            if record is None:
                return
        chunk_count = await index_document(record)
        update_job(job_id, "completed", f"Document refreshed. {chunk_count} text sections added.")
    except Exception as exc:
        logger.exception("Document re-index failed for %s", document_id)
        user_error = _classify_conversion_error(exc)
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
