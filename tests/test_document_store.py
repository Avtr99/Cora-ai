import os
from io import BytesIO
from pathlib import Path
from unittest import mock

import pytest
from fastapi import UploadFile


@pytest.fixture()
def document_store_env(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'cora.db'}")
    monkeypatch.setenv("DOCUMENT_STORE_ROOT", str(data_dir / "documents"))
    monkeypatch.setenv("ALLOWED_DOCUMENT_DIRS", str(data_dir))
    monkeypatch.setenv("DOCUMENT_ALLOWED_EXTENSIONS", ".pdf,.md,.txt,.csv,.json,.jsonl")
    monkeypatch.setenv("DOCUMENT_UPLOAD_MAX_BYTES", str(1024 * 1024))

    import src.config as config

    config.reset_settings_singleton()
    yield data_dir
    config.reset_settings_singleton()


@pytest.mark.asyncio
async def test_save_upload_persists_original_and_metadata(document_store_env):
    from src.document_store.storage import get_document, list_documents, save_upload

    upload = UploadFile(filename="Policy Draft.md", file=BytesIO(b"# Policy\n\nCarbon market text."))
    record = await save_upload(upload, "standard", ["policy", "client-a"])

    assert record.id.startswith("doc_")
    assert record.original_filename == "Policy_Draft.md"
    assert record.status == "queued"
    assert os.path.exists(record.original_path)
    assert os.path.exists(document_store_env / "documents" / "metadata" / f"{record.id}.json")

    stored = get_document(record.id)
    assert stored is not None
    assert stored.tags == ["policy", "client-a"]
    assert [doc.id for doc in list_documents()] == [record.id]


@pytest.mark.asyncio
async def test_text_conversion_writes_readable_markdown(document_store_env):
    from src.document_store.converter import convert_document, write_converted_markdown
    from src.document_store.storage import get_document, read_markdown, save_upload

    upload = UploadFile(filename="notes.txt", file=BytesIO(b"VCM notes for local knowledge base."))
    record = await save_upload(upload, "standard", [])

    result = await convert_document(record)
    write_converted_markdown(record, result)

    updated = get_document(record.id)
    assert updated is not None
    markdown = read_markdown(updated)
    assert "# notes" in markdown
    assert "VCM notes" in markdown


def test_parse_tags_deduplicates_and_limits_values(document_store_env):
    from src.document_store.storage import parse_tags

    assert parse_tags('["Legal", "legal", " Client-A "]') == ["legal", "client-a"]
    assert parse_tags("Policy, Methodology, policy") == ["policy", "methodology"]


@pytest.mark.asyncio
async def test_save_upload_rejects_duplicate_sha256(document_store_env):
    from src.document_store.storage import save_upload

    content = b"# Duplicate\n\nSame content."
    first = await save_upload(
        UploadFile(filename="original.md", file=BytesIO(content)), "standard", []
    )
    with pytest.raises(FileExistsError):
        await save_upload(
            UploadFile(filename="copy.md", file=BytesIO(content)), "standard", []
        )
    assert first.sha256


@pytest.mark.asyncio
async def test_delete_document_job_marks_document_deleted(document_store_env):
    from src.document_store.jobs import delete_document_job
    from src.document_store.storage import create_job, get_document, get_document_including_deleted, save_upload

    upload = UploadFile(filename="delete-me.txt", file=BytesIO(b"Delete me."))
    record = await save_upload(upload, "standard", [])
    job = create_job(record.id, "delete")

    with mock.patch("src.document_store.jobs.delete_document_chunks") as mock_chunks, mock.patch(
        "src.document_store.jobs.remove_document_files"
    ):
        mock_chunks.return_value = None
        await delete_document_job(record.id, job.id)

    updated = get_document(record.id)
    assert updated is None
    deleted = get_document_including_deleted(record.id)
    assert deleted is not None
    assert deleted.status == "deleted"


@pytest.mark.asyncio
async def test_delete_document_job_succeeds_when_already_deleted(document_store_env):
    from src.document_store.jobs import delete_document_job
    from src.document_store.storage import create_job, get_document_including_deleted, save_upload, update_document

    upload = UploadFile(filename="already-deleted.txt", file=BytesIO(b"Already deleted."))
    record = await save_upload(upload, "standard", [])
    update_document(record.id, status="deleted")
    job = create_job(record.id, "delete")

    # The fix ensures Qdrant cleanup runs even for already-soft-deleted docs
    # (previously the job exited early, leaving orphaned chunks behind).
    with mock.patch("src.document_store.jobs.delete_document_chunks") as mock_chunks, mock.patch(
        "src.document_store.jobs.remove_document_files"
    ):
        mock_chunks.return_value = None
        await delete_document_job(record.id, job.id)

    still_deleted = get_document_including_deleted(record.id)
    assert still_deleted is not None
    assert still_deleted.status == "deleted"
    # Qdrant cleanup must run even when the doc was already soft-deleted.
    mock_chunks.assert_called_once_with(record.id)


@pytest.mark.asyncio
async def test_delete_document_job_completes_when_qdrant_cleanup_fails(document_store_env):
    from src.document_store.jobs import delete_document_job
    from src.document_store.storage import create_job, get_document, get_document_including_deleted, save_upload

    upload = UploadFile(filename="qdrant-fail.txt", file=BytesIO(b"Qdrant cleanup fails."))
    record = await save_upload(upload, "standard", [])
    job = create_job(record.id, "delete")

    with mock.patch("src.document_store.jobs.delete_document_chunks") as mock_chunks, mock.patch(
        "src.document_store.jobs.remove_document_files"
    ):
        mock_chunks.side_effect = RuntimeError("Qdrant unavailable")
        await delete_document_job(record.id, job.id)

    updated = get_document(record.id)
    assert updated is None
    deleted = get_document_including_deleted(record.id)
    assert deleted is not None
    assert deleted.status == "deleted"


@pytest.mark.asyncio
async def test_recover_interrupted_documents_marks_in_flight_as_failed(document_store_env):
    """Priority 1: any document left in an in-flight status at startup must be
    flipped to failed so the UI shows a clear error instead of hanging forever.
    Jobs left in queued/processing must also be flipped to failed so the
    document_store_jobs table doesn't accumulate ghost rows."""
    from src.document_store.storage import (
        create_job,
        get_document_including_deleted,
        get_job,
        recover_interrupted_documents,
        save_upload,
        update_document,
        update_job,
    )

    records = []
    stuck_job_ids = []
    for name, status, job_status in [
        ("stuck-converting.txt", "converting", "processing"),
        ("stuck-indexing.txt", "indexing", "processing"),
        ("stuck-reading.txt", "reading", "processing"),
        ("stuck-deleting.txt", "deleting", "processing"),
        ("stuck-queued-job.txt", "queued", "queued"),
        ("healthy.txt", "indexed", "completed"),
        ("already-failed.txt", "failed", "failed"),
    ]:
        r = await save_upload(
            UploadFile(filename=name, file=BytesIO(f"{name} content".encode())),
            "standard",
            [],
        )
        if status != "queued":
            update_document(r.id, status=status)
        job = create_job(r.id, "process")
        if job_status != "queued":
            update_job(job.id, job_status)
        records.append((r.id, status))
        if job_status in ("queued", "processing"):
            stuck_job_ids.append(job.id)

    recovered = recover_interrupted_documents()
    assert recovered == 4  # the four in-flight document statuses

    for doc_id, original_status in records:
        doc = get_document_including_deleted(doc_id)
        assert doc is not None
        if original_status in ("converting", "indexing", "reading", "deleting"):
            assert doc.status == "failed"
            assert doc.error == "Interrupted by server restart"
        else:
            assert doc.status == original_status

    # Jobs stuck in queued/processing are flipped to failed.
    for job_id in stuck_job_ids:
        job = get_job(job_id)
        assert job is not None
        assert job.status == "failed"
        assert job.error == "Interrupted by server restart"

    # Idempotent: running again recovers nothing.
    assert recover_interrupted_documents() == 0


def test_get_conversion_capabilities_exposes_upload_limits(document_store_env):
    """Priority 3: /conversion-info must surface the server's allowed
    extensions and max_bytes so the frontend doesn't hardcode a parallel list."""
    from src.document_store.converter import get_conversion_capabilities

    caps = get_conversion_capabilities()
    limits = caps["upload_limits"]
    assert ".pdf" in limits["allowed_extensions"]
    assert ".md" in limits["allowed_extensions"]
    assert limits["max_bytes"] == 1024 * 1024  # set by the fixture


@pytest.mark.asyncio
async def test_update_document_skips_sidecar_for_transient_status(document_store_env):
    """Priority 4: update_document must only rewrite the metadata sidecar on
    terminal statuses, not on every transient state transition."""
    import json
    from pathlib import Path

    from src.document_store.storage import save_upload, update_document

    record = await save_upload(
        UploadFile(filename="sidecar.txt", file=BytesIO(b"sidecar test")),
        "standard",
        [],
    )
    sidecar = Path(record.original_path).parent.parent / "metadata" / f"{record.id}.json"
    assert sidecar.exists()  # written once by save_upload
    original_mtime = sidecar.stat().st_mtime_ns

    # Transient transition — should NOT rewrite the sidecar.
    update_document(record.id, status="converting")
    assert sidecar.stat().st_mtime_ns == original_mtime

    # Terminal transition — should rewrite the sidecar.
    update_document(record.id, status="indexed", chunk_count=3)
    assert sidecar.stat().st_mtime_ns != original_mtime
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert data["status"] == "indexed"
    assert data["chunk_count"] == 3


@pytest.mark.asyncio
async def test_docx_uploads_are_rejected(document_store_env):
    """DOCX is no longer an accepted format — the VLM pipeline can't handle it
    (no page rasterization) and structural parsing misses scanned content.
    Rejecting at upload is more honest than silently ignoring the mode."""
    from src.document_store.storage import save_upload

    with pytest.raises(ValueError, match="Unsupported file type"):
        await save_upload(
            UploadFile(filename="report.docx", file=BytesIO(b"PK\x03\x04docx content")),
            "standard",
            [],
        )


def test_conversion_capabilities_does_not_list_docx(document_store_env):
    """The upload_limits surfaced to the frontend must not include .docx or .html."""
    from src.document_store.converter import get_conversion_capabilities

    caps = get_conversion_capabilities()
    assert ".docx" not in caps["upload_limits"]["allowed_extensions"]
    assert ".html" not in caps["upload_limits"]["allowed_extensions"]
    assert ".htm" not in caps["upload_limits"]["allowed_extensions"]
    assert ".pdf" in caps["upload_limits"]["allowed_extensions"]


@pytest.mark.asyncio
async def test_html_uploads_are_rejected(document_store_env):
    """HTML is no longer an accepted format — the converter's HTML backend silently
    drops all images (placeholders with no content), which gives a false sense
    of completeness for VCM documents that contain diagrams and charts.
    Rejecting at upload pushes users to PDF, where the conversion pipeline can handle
    visual content."""
    from src.document_store.storage import save_upload

    with pytest.raises(ValueError, match="Unsupported file type"):
        await save_upload(
            UploadFile(filename="page.html", file=BytesIO(b"<html><body>content</body></html>")),
            "standard",
            [],
        )


# --- R3: error classification tests ---

def test_classify_conversion_error_import_error(document_store_env):
    """ImportError → user-friendly 'missing dependencies' message with actionable reinstall hint."""
    from src.document_store.jobs import _classify_conversion_error

    msg = _classify_conversion_error(ImportError("pymupdf not found"))
    assert "missing dependencies" in msg.lower()
    assert "pip install -r requirements.txt" in msg.lower()


def test_classify_conversion_error_docling_import_error(document_store_env):
    """ImportError mentioning docling/rapidocr → Docling-aware reinstall hint."""
    from src.document_store.jobs import _classify_conversion_error

    msg = _classify_conversion_error(ImportError("docling not found"))
    assert "docling" in msg.lower()
    assert "pip install -r requirements.txt" in msg.lower()

    msg2 = _classify_conversion_error(ImportError("No module named 'rapidocr'"))
    assert "docling" in msg2.lower()


def test_classify_conversion_error_value_error_passes_through(document_store_env):
    """ValueError messages from the converter are already user-friendly — pass through."""
    from src.document_store.jobs import _classify_conversion_error

    msg = _classify_conversion_error(
        ValueError("High-accuracy AI conversion requires a configured LLM provider.")
    )
    assert "configured LLM provider" in msg


def test_classify_conversion_error_httpx_401(document_store_env):
    """HTTP 401 → 'API key is invalid or expired'."""
    import httpx

    from src.document_store.jobs import _classify_conversion_error

    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(401, request=request, content=b'{"error": "invalid api key"}')
    exc = httpx.HTTPStatusError("401 Unauthorized", request=request, response=response)

    msg = _classify_conversion_error(exc)
    assert "api key" in msg.lower()
    assert "settings" in msg.lower()


def test_classify_conversion_error_httpx_429(document_store_env):
    """HTTP 429 → 'Rate limited' message."""
    import httpx

    from src.document_store.jobs import _classify_conversion_error

    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(429, request=request, content=b'{"error": "rate limited"}')
    exc = httpx.HTTPStatusError("429 Too Many Requests", request=request, response=response)

    msg = _classify_conversion_error(exc)
    assert "rate limited" in msg.lower()


def test_classify_conversion_error_httpx_timeout(document_store_env):
    """Timeout → 'Conversion timed out' message."""
    import httpx

    from src.document_store.jobs import _classify_conversion_error

    msg = _classify_conversion_error(httpx.ReadTimeout("timed out"))
    assert "timed out" in msg.lower()
    assert "standard mode" in msg.lower()


def test_classify_conversion_error_generic_fallback(document_store_env):
    """Unknown exceptions → include exception type name for log grepability."""
    from src.document_store.jobs import _classify_conversion_error

    msg = _classify_conversion_error(RuntimeError("something weird happened"))
    assert "RuntimeError" in msg
    assert "server logs" in msg.lower() or "standard mode" in msg.lower()


def test_classify_conversion_error_pymupdf_file_data_error(document_store_env):
    """PyMuPDF FileDataError → 'corrupted or password-protected' message."""
    import fitz

    from src.document_store.jobs import _classify_conversion_error

    msg = _classify_conversion_error(fitz.FileDataError("broken pdf"))
    assert "corrupted" in msg.lower() or "password-protected" in msg.lower()


def test_classify_conversion_error_pymupdf_empty_file(document_store_env):
    """PyMuPDF EmptyFileError → 'file is empty' message."""
    import fitz

    from src.document_store.jobs import _classify_conversion_error

    msg = _classify_conversion_error(fitz.EmptyFileError("empty"))
    assert "empty" in msg.lower()


# --- R4: configurable VLM prompt tests ---

def test_conversion_capabilities_exposes_llm_conversion_prompt(document_store_env):
    """R4: /conversion-info must surface the current conversion prompt so the
    frontend can display it (and eventually let users edit it)."""
    from src.document_store.converter import get_conversion_capabilities

    caps = get_conversion_capabilities()
    prompt = caps["llm_api"].get("conversion_prompt")
    assert prompt is not None
    assert "Markdown" in prompt
    assert "headings" in prompt


def test_conversion_prompt_is_configurable_via_env(document_store_env, monkeypatch):
    """R4: overriding DOCUMENT_LLM_CONVERSION_PROMPT via .env changes the prompt
    surfaced in /conversion-info and used by the converter."""
    import src.config as config

    custom_prompt = "Extract all VCM registry tables and methodology numbers. Return Markdown only."
    monkeypatch.setenv("DOCUMENT_LLM_CONVERSION_PROMPT", custom_prompt)
    config.reset_settings_singleton()

    from src.document_store.converter import get_conversion_capabilities

    caps = get_conversion_capabilities()
    assert caps["llm_api"]["conversion_prompt"] == custom_prompt

    config.reset_settings_singleton()


# --- R2: Docling standard (classical) conversion tests ---
# The standard path is mocked — no real Docling install or model download is
# required. PyMuPDF is still used to fabricate born-digital PDFs for the llm_api
# tests below (it renders pages to images there).

def _make_born_digital_pdf(path: Path, pages: int = 3) -> None:
    """Create a born-digital PDF with extractable text using PyMuPDF."""
    import fitz

    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i + 1} text content for testing. " * 5)
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


def test_convert_pdf_with_docling_standard_extracts_text(document_store_env, tmp_path):
    """_convert_pdf_with_docling_standard returns markdown + page_count from the
    Docling singleton, and forwards the max_num_pages/max_file_size bounds."""
    from src.document_store.converter import _convert_pdf_with_docling_standard

    pdf_path = tmp_path / "born_digital.pdf"
    _make_born_digital_pdf(pdf_path, pages=2)

    fake = _FakeDoclingConverter(markdown="# Heading\n\nPage 1 text. Page 2 text.", num_pages=2)
    with mock.patch("src.api.lifespan.get_docling_converter", return_value=fake):
        result = _convert_pdf_with_docling_standard(pdf_path)

    assert result.page_count == 2
    assert "Page 1 text" in result.markdown
    # The memory bounds from settings are forwarded to convert().
    assert fake.convert_calls[0]["max_num_pages"] is not None
    assert fake.convert_calls[0]["max_file_size"] is not None
    assert fake.convert_calls[0]["source"] == str(pdf_path)


def test_convert_pdf_with_docling_standard_warns_on_empty(document_store_env, tmp_path):
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


def test_convert_pdf_with_docling_standard_missing_deps_raises(document_store_env, tmp_path):
    """When the Docling singleton is None (not installed), standard mode raises an
    ImportError with a Docling-aware reinstall hint."""
    from src.document_store.converter import _convert_pdf_with_docling_standard

    pdf_path = tmp_path / "test.pdf"
    _make_born_digital_pdf(pdf_path, pages=1)

    with mock.patch("src.api.lifespan.get_docling_converter", return_value=None):
        with pytest.raises(ImportError, match="Docling standard parsing dependencies"):
            _convert_pdf_with_docling_standard(pdf_path)


def _make_scanned_like_pdf(path: Path, pages: int = 3) -> None:
    """Create a PDF whose pages have no native text layer (blank/image-only)."""
    import fitz

    doc = fitz.open()
    for _ in range(pages):
        doc.new_page()
    doc.save(str(path))
    doc.close()


def test_convert_pdf_docling_standard_warns_on_scanned_doc(document_store_env, tmp_path):
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


def test_convert_pdf_docling_standard_no_scanned_warning_for_born_digital(
    document_store_env, tmp_path
):
    """Born-digital PDFs (native text layer on every page) get no scanned warning."""
    from src.document_store.converter import _convert_pdf_with_docling_standard

    pdf_path = tmp_path / "digital.pdf"
    _make_born_digital_pdf(pdf_path, pages=2)

    fake = _FakeDoclingConverter(markdown="# Heading\n\nNative text.", num_pages=2)
    with mock.patch("src.api.lifespan.get_docling_converter", return_value=fake):
        result = _convert_pdf_with_docling_standard(pdf_path)

    assert result.warnings == []


def test_recover_flattened_formulas_replaces_placeholders(document_store_env):
    """Formula placeholders are replaced in document order with hedged,
    NFKC-normalized text from FormulaItem.orig (𝐹𝑖𝑛𝑎𝑙 𝐵𝐿𝑅𝑦 → Final BLRy)."""
    docling_core = pytest.importorskip("docling_core.types.doc")
    from types import SimpleNamespace

    from src.document_store.converter import _recover_flattened_formulas

    formula_label = docling_core.DocItemLabel.FORMULA
    items = [
        SimpleNamespace(label=formula_label, text="", orig="\U0001d439\U0001d456\U0001d45b\U0001d44e\U0001d459 \U0001d435\U0001d43f\U0001d445 \U0001d466 = min(BLR y , 25%)"),
        SimpleNamespace(label=formula_label, text="", orig="PLR y = L y,s / C y,s"),
        # Enriched formula (has LaTeX text) — serializer emits $$...$$, no placeholder.
        SimpleNamespace(label=formula_label, text="E = mc^2", orig="E = mc2"),
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


def test_recover_flattened_formulas_keeps_placeholders_on_mismatch(document_store_env):
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


def test_docling_available_false_when_not_installed(document_store_env):
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


def test_conversion_capabilities_standard_reports_docling(document_store_env):
    """The standard capability advertises Docling (provider/model), not PyMuPDF."""
    from src.document_store.converter import get_conversion_capabilities

    caps = get_conversion_capabilities()
    std = caps["standard"]
    assert std["provider"] == "docling"
    assert std["model"] == "docling-standard-classical"
    assert std["privacy"] == "local"
    assert std["speed"] == "fast"


# --- R2b: llm_api direct HTTP tests ---

def test_extract_llm_choice_text_string_content(document_store_env):
    """_extract_llm_choice_text handles standard string content responses."""
    from src.document_store.converter import _extract_llm_choice_text

    data = {"choices": [{"message": {"content": "# Heading\n\nMarkdown text."}}]}
    assert _extract_llm_choice_text(data) == "# Heading\n\nMarkdown text."


def test_extract_llm_choice_text_list_content(document_store_env):
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


def test_extract_llm_choice_text_empty_choices(document_store_env):
    """_extract_llm_choice_text returns empty string for empty choices."""
    from src.document_store.converter import _extract_llm_choice_text

    assert _extract_llm_choice_text({}) == ""
    assert _extract_llm_choice_text({"choices": []}) == ""


@pytest.mark.asyncio
async def test_convert_pdf_with_llm_api_mocked_http(document_store_env, tmp_path):
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
async def test_convert_pdf_with_llm_api_no_provider_raises(document_store_env, tmp_path):
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


# --- R2c: local_vlm mode removal test ---

@pytest.mark.asyncio
async def test_convert_document_rejects_local_vlm_mode(document_store_env, tmp_path):
    """Requesting local_vlm mode raises ValueError pointing to standard or llm_api."""
    from src.document_store import converter
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
        conversion_mode="local_vlm",
        original_path=str(pdf_path),
    )
    # Mock update_document — it's called before the mode check and needs the DB.
    with mock.patch.object(converter, "update_document"):
        with pytest.raises(ValueError, match="local_vlm mode has been removed") as exc_info:
            await converter.convert_document(record)
    # The removal message now points to Docling (standard), not PyMuPDF.
    assert "Docling" in str(exc_info.value)
