"""User-facing conversion error classification.

Translates raw exceptions raised by the converter (Docling, PyMuPDF, httpx,
the LLM API path, MemoryError, ImportError) into actionable messages shown in
the document's ``error`` field and the UI. The raw exception is still logged
by the caller via ``logger.exception``; these functions only control what the
user sees.

Extracted from ``jobs.py`` so the job handlers can stay focused on
orchestration. ``jobs.py`` re-exports ``_classify_conversion_error`` so
existing ``from src.document_store.jobs import _classify_conversion_error``
import sites keep working.
"""

from __future__ import annotations

import re

try:
    from docling.exceptions import ConversionError as _DoclingConversionError
except Exception:  # pragma: no cover - docling may not be installed in all environments
    _DoclingConversionError = None


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

    # MemoryError -- the host ran out of RAM during conversion
    if isinstance(exc, MemoryError):
        return (
            "Server ran out of memory while converting this PDF. "
            "Try a smaller file, lower DOCUMENT_DOCLING_TIMEOUT, "
            "or use llm_api mode for large/scanned documents."
        )

    # ImportError -- Docling (standard) or PyMuPDF (llm_api rendering) missing/broken
    if isinstance(exc, ImportError):
        low = exc_str.lower()
        if "docling" in low or "rapidocr" in low or "onnxtr" in low or "tesserocr" in low:
            return "Docling standard parsing dependencies are missing. Reinstall with `pip install -r requirements.txt`."
        if "fitz" in low or "pymupdf" in low:
            return "PyMuPDF is missing. Server is missing dependencies for PDF conversion. Reinstall with `pip install -r requirements.txt`."
        return "Server is missing dependencies for this conversion mode. Reinstall with `pip install -r requirements.txt`."

    # ValueError -- already user-friendly messages from the converter (e.g.
    # PARTIAL_SUCCESS timeout handling in _convert_pdf_with_docling_standard).
    if isinstance(exc, ValueError):
        return exc_str

    # httpx errors -- the llm_api path makes direct HTTP calls to the AI provider
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
        pass  # httpx not installed -- fall through to generic handling

    # PyMuPDF errors -- corrupted, empty, or password-protected PDFs
    try:
        import fitz

        if isinstance(exc, fitz.EmptyFileError):
            return "This PDF file is empty. Check the file and re-upload."
        if isinstance(exc, fitz.FileDataError):
            return "This PDF could not be parsed. It may be corrupted or password-protected. Try re-saving it as a new PDF."
    except ImportError:
        pass

    # Docling ConversionError -- surface the actual message so the user sees the
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
