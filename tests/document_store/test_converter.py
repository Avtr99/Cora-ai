"""Tests for the document converter and conversion capabilities."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
from fastapi import UploadFile


def _make_born_digital_pdf(path: Path, pages: int = 3) -> None:
    """Create a born-digital PDF with extractable text using PyMuPDF."""
    import fitz

    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i + 1} text content for testing. " * 5)
    doc.save(str(path))
    doc.close()


def _make_scanned_like_pdf(path: Path, pages: int = 3) -> None:
    """Create a PDF whose pages have no native text layer (blank/image-only)."""
    import fitz

    doc = fitz.open()
    for _ in range(pages):
        doc.new_page()
    doc.save(str(path))
    doc.close()


class _FakeDoclingDocument:
    """Minimal stand-in for docling's DoclingDocument for mocked tests."""

    def __init__(self, markdown: str, num_pages: int, items: list | None = None) -> None:
        self._markdown = markdown
        self.pages = [object() for _ in range(num_pages)]
        self._items = items or []

    def export_to_markdown(self) -> str:
        return self._markdown

    def iterate_items(self):
        for item in self._items:
            yield item, 0


class _FakeDoclingResult:
    """Minimal stand-in for docling's ConversionResult."""

    def __init__(self, markdown: str, num_pages: int) -> None:
        self.document = _FakeDoclingDocument(markdown, num_pages)
        self.errors = []
        try:
            from docling.datamodel.base_models import ConversionStatus

            self.status = ConversionStatus.SUCCESS
        except ImportError:
            self.status = "success"


class _FakeDoclingConverter:
    """Stand-in DocumentConverter whose convert() returns a canned result."""

    def __init__(self, markdown: str, num_pages: int) -> None:
        self._result = _FakeDoclingResult(markdown, num_pages)
        self.convert_calls: list[dict] = []

    def convert(self, source=None, max_num_pages=None, max_file_size=None, **kwargs):
        self.convert_calls.append(
            {
                "source": source,
                "max_num_pages": max_num_pages,
                "max_file_size": max_file_size,
            }
        )
        return self._result


@pytest.mark.asyncio
async def test_text_conversion_writes_readable_markdown(document_store_env):
    from src.document_store.converter import convert_document, write_converted_markdown
    from src.document_store.files import read_markdown
    from src.document_store.repository import get_document
    from src.document_store.uploads import save_upload

    upload = UploadFile(filename="notes.txt", file=BytesIO(b"VCM notes for local knowledge base."))
    record = await save_upload(upload, "standard", [])

    result = await convert_document(record)
    write_converted_markdown(record, result)

    updated = get_document(record.id)
    assert updated is not None
    markdown = read_markdown(updated)
    assert "# notes" in markdown
    assert "VCM notes" in markdown


def test_structured_conversion_keeps_only_nonempty_mapping_rows(tmp_path):
    from src.document_store.converter import _convert_json, _convert_jsonl

    json_path = tmp_path / "records.json"
    json_path.write_text(
        '[{"Project ID": "VCS1"}, {}, null, "not a row"]',
        encoding="utf-8",
    )
    json_result = _convert_json(json_path, "records")
    assert json_result.row_records == [{"Project ID": "VCS1"}]

    jsonl_path = tmp_path / "records.jsonl"
    jsonl_path.write_text(
        '{"Project ID": "VCS1"}\n{}\nnull\n',
        encoding="utf-8",
    )
    jsonl_result = _convert_jsonl(jsonl_path, "records")
    assert jsonl_result.row_records == [{"Project ID": "VCS1"}]


def test_convert_csv_preserves_leading_zero_identifiers(tmp_path):
    """CSV cells are read as strings so identifiers like '007' keep their
    leading zeros instead of being coerced to integers by pandas."""
    pytest.importorskip("pandas")
    from src.document_store.converter import _convert_csv

    csv_path = tmp_path / "projects.csv"
    csv_path.write_text(
        "Project ID,Name,Credits\n007,Alpha,100\n0123,Beta,\n",
        encoding="utf-8",
    )

    result = _convert_csv(csv_path, "projects")
    assert result.row_records == [
        {"Project ID": "007", "Name": "Alpha", "Credits": "100"},
        {"Project ID": "0123", "Name": "Beta", "Credits": ""},
    ]
    assert "007" in result.markdown
    assert result.rows_truncated is False


def test_convert_csv_marks_rows_truncated_at_row_cap(tmp_path):
    """A CSV beyond the ingestion row cap is converted as a prefix and flagged
    so the row sidecar and structured retrieval treat counts as lower bounds."""
    pytest.importorskip("pandas")
    from src.document_store.converter import _CSV_MAX_ROWS, _convert_csv

    csv_path = tmp_path / "big.csv"
    with csv_path.open("w", encoding="utf-8") as handle:
        handle.write("Project ID,Name\n")
        for i in range(_CSV_MAX_ROWS + 1):
            handle.write(f"P{i},project {i}\n")

    result = _convert_csv(csv_path, "big")
    assert result.rows_truncated is True
    assert len(result.row_records) == _CSV_MAX_ROWS
    assert any("50,000 rows" in w for w in result.warnings)


def test_get_conversion_capabilities_exposes_upload_limits(document_store_env):
    """Priority 3: /conversion-info must surface the server's allowed
    extensions and max_bytes so the frontend doesn't hardcode a parallel list."""
    from src.document_store.converter import get_conversion_capabilities

    caps = get_conversion_capabilities()
    limits = caps["upload_limits"]
    assert ".pdf" in limits["allowed_extensions"]
    assert ".md" in limits["allowed_extensions"]
    assert limits["max_bytes"] == 1024 * 1024  # set by the fixture


def test_conversion_capabilities_does_not_list_docx(document_store_env):
    """The upload_limits surfaced to the frontend must not include .docx or .html."""
    from src.document_store.converter import get_conversion_capabilities

    caps = get_conversion_capabilities()
    assert ".docx" not in caps["upload_limits"]["allowed_extensions"]
    assert ".html" not in caps["upload_limits"]["allowed_extensions"]
    assert ".htm" not in caps["upload_limits"]["allowed_extensions"]
    assert ".pdf" in caps["upload_limits"]["allowed_extensions"]


def test_conversion_capabilities_exposes_llm_conversion_prompt():
    """R4: /conversion-info must surface the current conversion prompt so the
    frontend can display it (and eventually let users edit it)."""
    from src.document_store.converter import get_conversion_capabilities

    caps = get_conversion_capabilities()
    prompt = caps["llm_api"].get("conversion_prompt")
    assert prompt is not None
    assert "Markdown" in prompt
    assert "headings" in prompt


def test_conversion_prompt_is_configurable_via_env(monkeypatch):
    """R4: overriding DOCUMENT_LLM_CONVERSION_PROMPT via .env changes the prompt
    surfaced in /conversion-info and used by the converter."""
    from src.config import reset_settings_singleton
    from src.document_store.converter import get_conversion_capabilities

    custom_prompt = "Extract all VCM registry tables and methodology numbers. Return Markdown only."
    monkeypatch.setenv("DOCUMENT_LLM_CONVERSION_PROMPT", custom_prompt)
    reset_settings_singleton()

    caps = get_conversion_capabilities()
    assert caps["llm_api"]["conversion_prompt"] == custom_prompt

    reset_settings_singleton()


def test_convert_pdf_with_docling_standard_extracts_text(tmp_path):
    """_convert_pdf_with_docling_standard returns markdown + page_count from the
    Docling singleton, and forwards the max_file_size bound."""
    from src.document_store.converter import _convert_pdf_with_docling_standard

    pdf_path = tmp_path / "born_digital.pdf"
    _make_born_digital_pdf(pdf_path, pages=2)

    fake = _FakeDoclingConverter(markdown="# Heading\n\nPage 1 text. Page 2 text.", num_pages=2)
    with mock.patch("src.api.lifespan.get_docling_converter", return_value=fake):
        result = _convert_pdf_with_docling_standard(pdf_path)

    assert result.page_count == 2
    assert "Page 1 text" in result.markdown
    # No hard page cap is passed; the file size bound is forwarded.
    assert fake.convert_calls[0]["max_num_pages"] is None
    assert fake.convert_calls[0]["max_file_size"] is not None
    assert fake.convert_calls[0]["source"] == str(pdf_path)


def test_convert_pdf_with_docling_standard_warns_on_empty(tmp_path):
    """An empty Docling markdown output produces a warning pointing to llm_api."""
    from src.document_store.converter import _convert_pdf_with_docling_standard

    pdf_path = tmp_path / "empty.pdf"
    _make_born_digital_pdf(pdf_path, pages=1)

    fake = _FakeDoclingConverter(markdown="   ", num_pages=1)
    with mock.patch("src.api.lifespan.get_docling_converter", return_value=fake):
        result = _convert_pdf_with_docling_standard(pdf_path)

    assert result.page_count == 1
    assert len(result.warnings) == 1
    assert "llm_api" in result.warnings[0]


def test_convert_pdf_with_docling_standard_missing_deps_raises(tmp_path):
    """When the Docling singleton is None (not installed), standard mode raises an
    ImportError with a Docling-aware reinstall hint."""
    from src.document_store.converter import _convert_pdf_with_docling_standard

    pdf_path = tmp_path / "test.pdf"
    _make_born_digital_pdf(pdf_path, pages=1)

    with mock.patch("src.api.lifespan.get_docling_converter", return_value=None):
        with pytest.raises(ImportError, match="Docling standard parsing dependencies"):
            _convert_pdf_with_docling_standard(pdf_path)


def test_convert_pdf_with_docling_standard_partial_timeout(tmp_path):
    """Docling PARTIAL_SUCCESS due to timeout raises a clear ValueError."""
    from docling.datamodel.base_models import ConversionStatus, FailureCategory
    from src.document_store.converter import _convert_pdf_with_docling_standard

    class _FakeTimeoutConverter:
        def __init__(self) -> None:
            self.convert_calls: list[dict] = []

        def convert(self, source=None, max_file_size=None, **kwargs):
            self.convert_calls.append({"source": source, "max_file_size": max_file_size})
            result = mock.MagicMock()
            result.status = ConversionStatus.PARTIAL_SUCCESS
            timeout_error = mock.MagicMock()
            timeout_error.error_message = (
                "Document processing timeout: exceeded 1800.000s limit after "
                "1810.000s. Processed 50/100 pages."
            )
            timeout_error.category = FailureCategory.TIMEOUT
            result.errors = [timeout_error]
            result.document.export_to_markdown.return_value = "Partial content."
            return result

    pdf_path = tmp_path / "big.pdf"
    _make_born_digital_pdf(pdf_path, pages=1)

    fake = _FakeTimeoutConverter()
    with mock.patch("src.api.lifespan.get_docling_converter", return_value=fake):
        with pytest.raises(ValueError, match="timed out") as exc_info:
            _convert_pdf_with_docling_standard(pdf_path)

    msg = str(exc_info.value)
    assert "Processed 50/100 pages" in msg
    assert "DOCUMENT_DOCLING_TIMEOUT" in msg
    assert "LLM API" in msg
    assert fake.convert_calls[0]["max_file_size"] is not None
    assert fake.convert_calls[0].get("max_num_pages") is None


def test_convert_pdf_docling_standard_warns_on_scanned_doc(tmp_path):
    """When most pages lack a native text layer but OCR still extracted text,
    a scanned-document warning suggesting llm_api is attached."""
    from src.document_store.converter import _convert_pdf_with_docling_standard

    pdf_path = tmp_path / "scanned.pdf"
    _make_scanned_like_pdf(pdf_path, pages=3)

    fake = _FakeDoclingConverter(markdown="Text recovered by OCR from scans.", num_pages=3)
    with mock.patch("src.api.lifespan.get_docling_converter", return_value=fake):
        result = _convert_pdf_with_docling_standard(pdf_path)

    assert len(result.warnings) == 1
    assert "appears to be scanned" in result.warnings[0]
    assert "llm_api" in result.warnings[0]


def test_convert_pdf_docling_standard_no_scanned_warning_for_born_digital(tmp_path):
    """Born-digital PDFs (native text layer on every page) get no scanned warning."""
    from src.document_store.converter import _convert_pdf_with_docling_standard

    pdf_path = tmp_path / "digital.pdf"
    _make_born_digital_pdf(pdf_path, pages=2)

    fake = _FakeDoclingConverter(markdown="# Heading\n\nNative text.", num_pages=2)
    with mock.patch("src.api.lifespan.get_docling_converter", return_value=fake):
        result = _convert_pdf_with_docling_standard(pdf_path)

    assert result.warnings == []


def test_recover_flattened_formulas_replaces_placeholders():
    """Formula placeholders are replaced in document order with hedged,
    NFKC-normalized text from FormulaItem.orig."""
    pytest.importorskip("docling_core.types.doc")
    from src.document_store.converter import _recover_flattened_formulas

    from docling_core.types.doc import DocItemLabel

    items = [
        SimpleNamespace(
            label=DocItemLabel.FORMULA,
            text="",
            orig="\U0001d439\U0001d456\U0001d45b\U0001d44e\U0001d459 \U0001d435\U0001d43f\U0001d445 \U0001d466 = min(BLR y , 25%)",
        ),
        SimpleNamespace(
            label=DocItemLabel.FORMULA,
            text="",
            orig="PLR y = L y,s / C y,s",
        ),
        # Enriched formula (has LaTeX text) -- serializer emits $$...$$, no placeholder.
        SimpleNamespace(
            label=DocItemLabel.FORMULA,
            text="E = mc^2",
            orig="E = mc2",
        ),
    ]
    doc = _FakeDoclingDocument(
        markdown=(
            "## 8.1 Baseline\n\n<!-- formula-not-decoded -->\n\nWhere:\n\n"
            "## 8.2 Project\n\n<!-- formula-not-decoded -->\n\n$$E = mc^2$$"
        ),
        num_pages=2,
        items=items,
    )

    out = _recover_flattened_formulas(doc, doc.export_to_markdown())

    assert "<!-- formula-not-decoded -->" not in out
    assert "[Formula (extracted as flattened text; fraction/summation layout may be lost): Final BLR y = min(BLR y , 25%)]" in out
    assert "layout may be lost): PLR y = L y,s / C y,s]" in out
    assert "$$E = mc^2$$" in out  # enriched formula untouched


def test_recover_flattened_formulas_keeps_placeholders_on_mismatch():
    """If placeholder and formula-item counts disagree, the markdown is returned
    unchanged rather than risking splicing text into the wrong location."""
    pytest.importorskip("docling_core.types.doc")
    from src.document_store.converter import _recover_flattened_formulas

    doc = _FakeDoclingDocument(
        markdown="Intro\n\n<!-- formula-not-decoded -->\n\nOutro",
        num_pages=1,
        items=[],  # no formula items, but one placeholder
    )

    out = _recover_flattened_formulas(doc, doc.export_to_markdown())
    assert out == doc.export_to_markdown()


def test_docling_available_false_when_not_installed():
    """_docling_available() returns False when the docling package can't import."""
    from src.document_store import converter

    with mock.patch.dict("sys.modules", {"docling": None}):
        # Force the import inside _docling_available to fail.
        import builtins

        real_import = builtins.__import__

        def _fail_docling(name, *args, **kwargs):
            if name == "docling":
                raise ImportError("no docling")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=_fail_docling):
            assert converter._docling_available() is False


def test_conversion_capabilities_standard_reports_docling():
    """The standard capability advertises Docling (provider/model), not PyMuPDF."""
    from src.document_store.converter import get_conversion_capabilities

    caps = get_conversion_capabilities()
    std = caps["standard"]
    assert std["provider"] == "docling"
    assert std["model"] == "docling-standard-classical"
    assert std["privacy"] == "local"
    assert std["speed"] == "fast"


def test_conversion_capabilities_standard_available_with_worker_dispatch(monkeypatch):
    """In worker-dispatch mode, standard is available even if Docling is not
    installed in the query-only app container. The worker is the one with the
    full parser stack."""
    from src.config import reset_settings_singleton
    from src.document_store.converter import get_conversion_capabilities

    monkeypatch.setenv("INGESTION_DISPATCH", "worker")
    reset_settings_singleton()

    with mock.patch("src.document_store.converter._docling_available", return_value=False):
        caps = get_conversion_capabilities()
        assert caps["standard"]["available"] is True

    reset_settings_singleton()


def test_conversion_capabilities_standard_unavailable_in_process_without_docling():
    """In in_process mode, standard is only available when Docling is local."""
    from src.document_store.converter import get_conversion_capabilities

    with mock.patch("src.document_store.converter._docling_available", return_value=False):
        caps = get_conversion_capabilities()
        assert caps["standard"]["available"] is False


def test_extract_llm_choice_text_string_content():
    """_extract_llm_choice_text handles standard string content responses."""
    from src.document_store.converter import _extract_llm_choice_text

    data = {"choices": [{"message": {"content": "# Heading\n\nMarkdown text."}}]}
    assert _extract_llm_choice_text(data) == "# Heading\n\nMarkdown text."


def test_extract_llm_choice_text_list_content():
    """_extract_llm_choice_text handles content-part list responses (some providers)."""
    from src.document_store.converter import _extract_llm_choice_text

    data = {
        "choices": [{
            "message": {
                "content": [
                    {"type": "text", "text": "Part 1."},
                    {"type": "text", "text": "Part 2."},
                ]
            }
        }]
    }
    result = _extract_llm_choice_text(data)
    assert "Part 1." in result
    assert "Part 2." in result


def test_extract_llm_choice_text_empty_choices():
    """_extract_llm_choice_text returns empty string for empty choices."""
    from src.document_store.converter import _extract_llm_choice_text

    assert _extract_llm_choice_text({}) == ""
    assert _extract_llm_choice_text({"choices": []}) == ""


@pytest.mark.asyncio
async def test_convert_pdf_with_llm_api_mocked_http(tmp_path):
    """_convert_pdf_with_llm_api renders pages, sends base64 images to the LLM
    endpoint via httpx, and reassembles per-page markdown into a single document.

    Mocks httpx.AsyncClient so no real HTTP call is made. Verifies:
    - page_count matches the PDF
    - markdown contains the LLM response text
    - warnings include the provider attribution message
    """
    from src.document_store import converter

    pdf_path = tmp_path / "test_llm.pdf"
    _make_born_digital_pdf(pdf_path, pages=2)

    # Mock the LLM provider resolution
    fake_provider = {
        "available": True,
        "provider": "openai",
        "api_key": "test-key",
        "model": "gpt-4.1-mini",
        "url": "https://api.openai.com/v1/chat/completions",
    }

    # Mock httpx.AsyncClient to return a fake response for each page
    class FakeResponse:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "# Mocked Page\n\nLLM text."}}]}

        def raise_for_status(self):
            pass

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            self.headers = kwargs.get("headers", {})

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, json=None, timeout=None):
            return FakeResponse()

    with mock.patch.object(converter, "_resolve_llm_provider", return_value=fake_provider), \
         mock.patch("httpx.AsyncClient", FakeAsyncClient):
        result = await converter._convert_pdf_with_llm_api(pdf_path)

    assert result.page_count == 2
    assert "Mocked Page" in result.markdown
    assert "LLM text." in result.markdown
    # Provider attribution warning
    assert any("openai" in w.lower() for w in result.warnings)


@pytest.mark.asyncio
async def test_convert_pdf_with_llm_api_no_provider_raises(tmp_path):
    """_convert_pdf_with_llm_api raises ValueError if no LLM provider is configured."""
    from src.document_store import converter

    pdf_path = tmp_path / "test_no_provider.pdf"
    _make_born_digital_pdf(pdf_path, pages=1)

    fake_provider = {
        "available": False,
        "provider": None,
        "api_key": None,
        "model": None,
        "url": None,
    }
    with mock.patch.object(converter, "_resolve_llm_provider", return_value=fake_provider):
        with pytest.raises(ValueError, match="configured LLM provider"):
            await converter._convert_pdf_with_llm_api(pdf_path)


@pytest.mark.asyncio
async def test_convert_document_rejects_local_vlm_mode(tmp_path):
    """Requesting local_vlm mode raises ValueError pointing to standard or llm_api."""
    from src.document_store.converter import convert_document
    from src.document_store.models import DocumentRecord

    pdf_path = tmp_path / "test.pdf"
    _make_born_digital_pdf(pdf_path)

    record = DocumentRecord(
        id="test-local-vlm",
        original_filename="test.pdf",
        stored_filename="test.pdf",
        mime_type="application/pdf",
        extension=".pdf",
        size_bytes=100,
        sha256="abc",
        status="queued",
        conversion_mode="local_vlm",  # type: ignore[arg-type]
        original_path=str(pdf_path),
    )
    # Mock update_document -- it's called before the mode check and needs the DB.
    with mock.patch("src.document_store.converter.update_document"):
        with pytest.raises(ValueError, match="local_vlm mode has been removed") as exc_info:
            await convert_document(record)
    # The removal message now points to Docling (standard), not PyMuPDF.
    assert "Docling" in str(exc_info.value)
