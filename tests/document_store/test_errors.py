"""Tests for conversion error classification."""
from __future__ import annotations

import httpx
import pytest

try:
    import fitz
except ImportError:
    fitz = None

try:
    from docling.exceptions import ConversionError as DoclingConversionError
except Exception:
    DoclingConversionError = None


_REQUEST = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
_401_RESPONSE = httpx.Response(401, request=_REQUEST, content=b'{"error": "invalid api key"}')
_429_RESPONSE = httpx.Response(429, request=_REQUEST, content=b'{"error": "rate limited"}')


_CASES = [
    pytest.param(
        ImportError("pymupdf not found"),
        "standard",
        ["missing dependencies", "pip install -r requirements.txt"],
        [],
        id="import_error_pymupdf",
    ),
    pytest.param(
        ImportError("docling not found"),
        "standard",
        ["docling", "pip install -r requirements.txt"],
        [],
        id="import_error_docling",
    ),
    pytest.param(
        ImportError("No module named 'rapidocr'"),
        "standard",
        ["docling", "pip install -r requirements.txt"],
        [],
        id="import_error_rapidocr",
    ),
    pytest.param(
        ValueError("High-accuracy AI conversion requires a configured LLM provider."),
        "standard",
        ["configured llm provider"],
        [],
        id="value_error_pass_through",
    ),
    pytest.param(
        httpx.HTTPStatusError("401 Unauthorized", request=_REQUEST, response=_401_RESPONSE),
        "standard",
        ["api key", "settings"],
        [],
        id="httpx_401",
    ),
    pytest.param(
        httpx.HTTPStatusError("429 Too Many Requests", request=_REQUEST, response=_429_RESPONSE),
        "standard",
        ["rate limited"],
        [],
        id="httpx_429",
    ),
    pytest.param(
        httpx.ReadTimeout("timed out"),
        "standard",
        ["timed out", "llm_api"],
        ["standard mode"],
        id="httpx_timeout_standard",
    ),
    pytest.param(
        httpx.ReadTimeout("timed out"),
        "llm_api",
        ["timed out", "standard mode"],
        ["llm_api"],
        id="httpx_timeout_llm_api",
    ),
    pytest.param(
        RuntimeError("something weird happened"),
        "llm_api",
        ["runtimeerror", "standard mode"],
        ["llm_api"],
        id="llm_api_fallback",
    ),
    pytest.param(
        RuntimeError("something weird happened"),
        "standard",
        ["runtimeerror", "server logs"],
        ["standard mode"],
        id="generic_fallback",
    ),
]

if fitz is not None:
    _CASES.append(
        pytest.param(
            fitz.FileDataError("broken pdf"),
            "standard",
            ["corrupted", "password-protected"],
            [],
            id="pymupdf_file_data",
        ),
    )
    _CASES.append(
        pytest.param(
            fitz.EmptyFileError("empty"),
            "standard",
            ["empty"],
            [],
            id="pymupdf_empty",
        ),
    )

if DoclingConversionError is not None:
    _CASES.append(
        pytest.param(
            DoclingConversionError(
                "Conversion failed for: doc.pdf with status: failure. "
                "Errors: Input size 123456789 exceeds max_file_size limit 50000000 bytes."
            ),
            "standard",
            ["123,456,789", "50,000,000", "file size", "document_docling_max_file_bytes", "standard mode"],
            [],
            id="docling_file_size_limit",
        ),
    )
    _CASES.append(
        pytest.param(
            DoclingConversionError(
                "Conversion failed for: doc.pdf with status: partial_success. "
                "Errors: Document processing timeout: exceeded 120.000s limit after 125.000s. "
                "Processed 50/100 pages."
            ),
            "standard",
            ["took too long", "llm api", "standard mode"],
            [],
            id="docling_timeout",
        ),
    )
    _CASES.append(
        pytest.param(
            DoclingConversionError(
                "Conversion failed for: doc.pdf with status: failure. "
                "Errors: The document backend could not parse the input."
            ),
            "standard",
            ["couldn't read this pdf", "corrupted", "llm api"],
            [],
            id="docling_backend_failure",
        ),
    )
    _CASES.append(
        pytest.param(
            DoclingConversionError(
                "Conversion failed for: doc.pdf with status: failure. "
                "Errors: File doc.pdf not found or cannot be opened."
            ),
            "standard",
            ["couldn't be opened", "re-upload"],
            [],
            id="docling_source_unavailable",
        ),
    )
    _CASES.append(
        pytest.param(
            DoclingConversionError(
                "Conversion failed for: doc.pdf with status: failure. "
                "Errors: Some obscure Docling pipeline failure."
            ),
            "standard",
            ["some obscure docling pipeline failure", "server logs", "llm api"],
            ["conversion failed for:"],
            id="docling_generic",
        ),
    )


@pytest.mark.parametrize(
    "exc, conversion_mode, expected_in, not_expected_in",
    _CASES,
)
def test_classify_conversion_error(exc, conversion_mode, expected_in, not_expected_in):
    """User-facing conversion error messages contain the right guidance."""
    from src.document_store.errors import _classify_conversion_error

    msg = _classify_conversion_error(exc, conversion_mode)
    for sub in expected_in:
        assert sub.lower() in msg.lower()
    for sub in not_expected_in:
        assert sub.lower() not in msg.lower()
