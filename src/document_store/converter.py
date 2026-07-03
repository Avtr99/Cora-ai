from __future__ import annotations

import asyncio
import base64
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from loguru import logger

from ..config import get_settings
from ..document_loader.metadata_extractor import get_metadata_extractor
from ..query_processing.llm_factory import get_llm_settings
from .models import DocumentRecord
from .storage import update_document
from .title_utils import _build_display_title, _clean_display_name, _extract_content_title

_TEXT_EXTENSIONS = {".md", ".txt"}
_STRUCTURED_TEXT_EXTENSIONS = {".csv", ".json", ".jsonl"}
_PDF_EXTENSIONS = {".pdf"}


class ConversionResult:
    def __init__(
        self,
        markdown: str,
        page_count: int | None = None,
        warnings: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.markdown = markdown
        self.page_count = page_count
        self.warnings = warnings or []
        self.metadata = metadata or {}


def _ensure_title(
    markdown: str,
    filename: str,
    metadata: dict[str, Any],
    extension: str = "",
) -> str:
    """Prepend the best human-readable title derived from content and filename.

    ``metadata`` is the VCM metadata extracted once by MetadataExtractor; the
    title is stored in it so callers can persist it without re-extracting.

    For uploaded Markdown files, an existing H1 is preserved as the document's
    top-level heading (the user wrote it intentionally). For other formats,
    the converter usually injects a filename-based placeholder H1, so it is
    replaced with the extracted title.
    """
    content_title = _extract_content_title(markdown, metadata.get("document_id"))
    title = _build_display_title(metadata, content_title, filename)
    if not title:
        return markdown
    # Store the final title back into metadata so the caller can persist it.
    metadata["title"] = title
    first_line = markdown.split("\n", 1)[0].strip()
    has_h1 = re.match(r"^#\s+", first_line) is not None
    is_markdown_file = extension.lower() == ".md"

    # Preserve user-authored H1s in Markdown files; replace placeholder H1s
    # produced by the converter for other formats.
    if is_markdown_file and has_h1:
        return markdown
    if has_h1:
        markdown = re.sub(r"^#\s+.*$", f"# {title}", markdown, count=1, flags=re.MULTILINE)
    else:
        markdown = f"# {title}\n\n{markdown}"
    return markdown


async def convert_document(record: DocumentRecord) -> ConversionResult:
    update_document(record.id, status="converting")
    extension = record.extension.lower()
    source_path = Path(record.original_path)
    display_name = _clean_display_name(record.original_filename)
    if extension in _TEXT_EXTENSIONS:
        result = await asyncio.to_thread(_convert_text_file, source_path, extension, display_name)
    elif extension in _STRUCTURED_TEXT_EXTENSIONS:
        result = await asyncio.to_thread(_convert_structured_text_file, source_path, extension, display_name)
    elif extension in _PDF_EXTENSIONS:
        if record.conversion_mode == "llm_api":
            result = await _convert_pdf_with_llm_api(source_path)
        elif record.conversion_mode == "local_vlm":
            raise ValueError(
                "local_vlm mode has been removed. Use 'standard' (Docling, free, CPU) "
                "or 'llm_api' (AI service, higher accuracy). For a local VLM, point "
                "llm_api at a local vLLM server via OPENAI_BASE_URL."
            )
        else:
            result = await asyncio.to_thread(_convert_pdf_with_docling_standard, source_path)
    else:
        raise ValueError(f"Unsupported file type: {extension}")

    # Extract VCM metadata once from the converted content + filename.
    # This is the single source of truth for registry, publisher, document_id,
    # version, and title — persisted to DocumentRecord and read by the indexer.
    metadata = get_metadata_extractor().extract(result.markdown, record.original_filename)
    result.markdown = _ensure_title(
        result.markdown, record.original_filename, metadata, extension=record.extension
    )
    result.metadata = metadata
    return result


def write_converted_markdown(record: DocumentRecord, result: ConversionResult) -> Path:
    if not record.converted_path:
        raise ValueError("Converted path is not configured")
    converted_path = Path(record.converted_path)
    converted_path.parent.mkdir(parents=True, exist_ok=True)
    converted_path.write_text(result.markdown.strip() + "\n", encoding="utf-8")
    update_document(
        record.id,
        converted_path=str(converted_path),
        page_count=result.page_count,
        warnings=result.warnings,
    )
    return converted_path


def _convert_text_file(path: Path, extension: str, display_name: str) -> ConversionResult:
    text = _read_text(path)
    if extension == ".md":
        return ConversionResult(text)
    return ConversionResult(f"# {display_name}\n\n```text\n{text}\n```")


def _convert_structured_text_file(path: Path, extension: str, display_name: str) -> ConversionResult:
    if extension == ".csv":
        return _convert_csv(path, display_name)
    if extension == ".jsonl":
        return _convert_jsonl(path, display_name)
    return _convert_json(path, display_name)


def _convert_csv(path: Path, display_name: str) -> ConversionResult:
    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError("CSV support requires pandas") from exc

    df = pd.read_csv(path, nrows=50000)
    if df.empty:
        return ConversionResult(f"# {path.name}\n\nThis CSV file is empty.")
    lines = [f"# {display_name}", "", f"Rows included: {len(df)}", "", "## Columns", ""]
    lines.extend(f"- {column}" for column in df.columns)
    lines.extend(["", "## Records", ""])
    for idx, row in df.fillna("").iterrows():
        parts = [f"{column}: {str(value).strip()}" for column, value in row.items() if str(value).strip()]
        if parts:
            lines.append(f"### Row {idx + 1}")
            lines.append("; ".join(parts))
            lines.append("")
    warnings = []
    if len(df) >= 50000:
        warnings.append("Only the first 50,000 rows were converted. Split very large files for best results.")
    return ConversionResult("\n".join(lines), warnings=warnings)


def _convert_json(path: Path, display_name: str) -> ConversionResult:
    data = json.loads(_read_text(path))
    return ConversionResult(f"# {display_name}\n\n```json\n{json.dumps(data, indent=2, ensure_ascii=False)}\n```")


def _convert_jsonl(path: Path, display_name: str) -> ConversionResult:
    lines = [f"# {display_name}", "", "## Records", ""]
    for idx, raw_line in enumerate(_read_text(path).splitlines(), start=1):
        if not raw_line.strip():
            continue
        data = json.loads(raw_line)
        lines.append(f"### Record {idx}")
        lines.append("```json")
        lines.append(json.dumps(data, indent=2, ensure_ascii=False))
        lines.append("```")
        lines.append("")
    return ConversionResult("\n".join(lines))


# Emitted by docling-core's Markdown serializer for detected formula regions
# when no VLM enrichment ran (see FormulaItem handling in serializer/markdown.py).
_DOCLING_FORMULA_PLACEHOLDER = "<!-- formula-not-decoded -->"

# A page whose native (non-OCR) text layer has fewer characters than this is
# treated as image-only/scanned for the coverage heuristic below.
_NATIVE_TEXT_MIN_CHARS_PER_PAGE = 100
# Warn when more than half the pages lack a native text layer.
_SCANNED_PAGE_FRACTION_THRESHOLD = 0.5


def _native_text_coverage(path: Path) -> float:
    """Fraction of pages with a usable native (non-OCR) text layer.

    Uses PyMuPDF (already installed for llm_api page rendering) to read the
    PDF's embedded text layer directly — independent of whatever Docling/OCR
    produced. Born-digital PDFs score ~1.0; scanned PDFs score ~0.0.
    """
    import fitz

    with fitz.open(str(path)) as pdf:
        if pdf.page_count == 0:
            return 1.0
        pages_with_text = sum(
            1
            for page in pdf
            if len(page.get_text("text").strip()) >= _NATIVE_TEXT_MIN_CHARS_PER_PAGE
        )
        return pages_with_text / pdf.page_count


def _recover_flattened_formulas(doc: Any, markdown: str) -> str:
    """Replace Docling's formula placeholders with hedged raw text-layer content.

    Docling's layout model detects formula regions, but without VLM enrichment
    its Markdown serializer discards the text extracted from the PDF text layer
    (kept in ``FormulaItem.orig``) and emits ``<!-- formula-not-decoded -->``.

    The flattened text is faithful for single-line formulas (e.g.
    ``Final BLRy = min(BLRy, CAP BLRy, 25%)``) but loses vertical layout —
    fraction bars and summation limits collapse, so ``× GWP / 1000`` can read
    as ``× GWP 1000``. The text is therefore wrapped in an explicit hedge
    marker so downstream LLMs treat it as approximate rather than authoritative
    math, while its tokens (variable names, operators) remain available for
    retrieval. NFKC normalization maps mathematical-alphanumeric glyphs
    (``𝐵𝐿𝑅𝑦``) to plain ASCII (``BLRy``) so embeddings and lexical matching
    line up with user queries.
    """
    if _DOCLING_FORMULA_PLACEHOLDER not in markdown:
        return markdown
    try:
        from docling_core.types.doc import DocItemLabel
    except ImportError:
        return markdown
    origs = [
        unicodedata.normalize("NFKC", item.orig).strip()
        for item, _level in doc.iterate_items()
        if getattr(item, "label", None) == DocItemLabel.FORMULA
        and not getattr(item, "text", "")
        and getattr(item, "orig", "")
    ]
    parts = markdown.split(_DOCLING_FORMULA_PLACEHOLDER)
    if len(parts) - 1 != len(origs):
        logger.warning(
            "Formula placeholder/item count mismatch ({} placeholders, {} items); "
            "keeping placeholders to avoid splicing text into the wrong location",
            len(parts) - 1,
            len(origs),
        )
        return markdown
    out = [parts[0]]
    for orig, tail in zip(origs, parts[1:]):
        out.append(
            f"[Formula (extracted as flattened text; fraction/summation layout "
            f"may be lost): {orig}]"
        )
        out.append(tail)
    return "".join(out)


def _convert_pdf_with_docling_standard(path: Path) -> ConversionResult:
    """Convert a PDF to Markdown via Docling's classical (non-VLM) pipeline.

    Runs the layout model + OCR (RapidOCR by default) + table structure
    (TableFormer). No VLM is loaded. The Docling ``DocumentConverter`` singleton
    is built lazily on first use (see ``lifespan.get_docling_converter``); models
    download on the first conversion if not pre-cached under
    ``DOCLING_ARTIFACTS_PATH``.

    ``max_num_pages`` and ``max_file_size`` bound memory on huge PDFs. For
    table-heavy or complex-layout documents where Markdown table fidelity is
    poor, ``llm_api`` mode is the higher-accuracy escape hatch.
    """
    from ..api.lifespan import get_docling_converter

    converter = get_docling_converter()
    if converter is None:
        raise ImportError(
            "Docling standard parsing dependencies are missing. "
            "Reinstall with `pip install -r requirements.txt`."
        )

    settings = get_settings()
    result = converter.convert(
        source=str(path),
        max_num_pages=settings.DOCUMENT_DOCLING_MAX_PAGES,
        max_file_size=settings.DOCUMENT_DOCLING_MAX_FILE_BYTES,
    )
    doc = result.document
    markdown = _recover_flattened_formulas(doc, doc.export_to_markdown())
    page_count = len(list(doc.pages))
    warnings: list[str] = []
    if not markdown.strip():
        warnings.append(
            "No text was extracted from any page. The PDF may be empty or "
            "password-protected — try llm_api mode for higher accuracy."
        )
    else:
        # Scanned-doc heuristic: if most pages have no native text layer, the
        # extracted text came from OCR and may be degraded. Best-effort — a
        # probe failure must never fail an otherwise successful conversion.
        try:
            coverage = _native_text_coverage(path)
        except Exception:
            logger.warning("Native text layer probe failed for {}", path.name)
            coverage = 1.0
        if coverage < _SCANNED_PAGE_FRACTION_THRESHOLD:
            scanned_pct = round((1 - coverage) * 100)
            warnings.append(
                f"This document appears to be scanned ({scanned_pct}% of pages have "
                "no native text layer). Text was recovered via OCR and may contain "
                "errors or gaps — consider re-uploading with llm_api mode for "
                "higher accuracy."
            )
    return ConversionResult(markdown, page_count=page_count, warnings=warnings)


def _resolve_llm_provider() -> dict[str, Any]:
    """Determine which LLM provider and model to use for high-accuracy PDF conversion.

    Reuses get_llm_settings() which auto-detects from DB settings or .env:
      - Gemini if GEMINI_API_KEY is set (preferred when both keys are present)
      - OpenAI-compatible if OPENAI_API_KEY is set

    Returns a dict with keys: provider, api_key, model, url, available.
    """
    llm_settings = get_llm_settings()
    provider = llm_settings.get("provider")
    api_key = llm_settings.get("api_key")

    if provider == "gemini" and api_key:
        model = llm_settings.get("model_main") or "gemini-2.5-flash"
        return {
            "provider": "gemini",
            "api_key": api_key,
            "model": model,
            "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            "available": True,
        }

    if provider == "openai_compatible" and api_key:
        base_url = llm_settings.get("base_url") or "https://api.openai.com/v1"
        if not base_url.endswith("/chat/completions"):
            base_url = base_url.rstrip("/") + "/chat/completions"
        model = llm_settings.get("model_main") or "gpt-4.1-mini"
        return {
            "provider": "openai",
            "api_key": api_key,
            "model": model,
            "url": base_url,
            "available": True,
        }

    return {
        "provider": None,
        "api_key": None,
        "model": None,
        "url": None,
        "available": False,
    }


def _docling_available() -> bool:
    """Best-effort probe: is Docling importable right now?

    Checks the top-level package only — the OCR engine extras (rapidocr/tesseract/
    onnxtr) are validated lazily on first conversion. This keeps the capability
    probe cheap and avoids importing heavy model deps on every /conversion-info call.
    """
    try:
        import docling  # noqa: F401
    except Exception:
        return False
    return True


def get_conversion_capabilities() -> dict[str, Any]:
    """Return the availability, resolved model, and metadata for each conversion mode.

    Used by the /v1/documents/conversion-info endpoint so the frontend can
    show which provider/model will be used, estimated cost, privacy implications,
    and disable unavailable modes.

    Each mode dict contains:
        available: bool        — whether this mode can be used right now
        model: str|None        — resolved model name
        provider: str|None     — resolved provider name (llm_api only)
        cost_per_page: str     — human-readable cost estimate per PDF page
        privacy: str           — "local" (no data leaves machine) or "external" (sent to API)
        speed: str             — "fast", "medium", "slow", or "very_slow"
        experimental: bool     — whether this mode is advanced/experimental
    """
    settings = get_settings()
    llm = _resolve_llm_provider()

    # Cost estimates (verified June 2026):
    #   Gemini 2.5 Flash:  $0.30/M input, $2.50/M output → ~$0.002/page
    #   GPT-4.1-mini:      $0.40/M input, $1.60/M output → ~$0.002/page
    llm_cost = "~$0.002 per page" if llm["available"] else "—"

    # ponytail: surface the server's actual upload constraints so the frontend
    # doesn't have to hardcode a parallel list. Single source of truth.
    allowed_extensions = sorted(
        ext.strip().lower()
        for ext in settings.DOCUMENT_ALLOWED_EXTENSIONS.split(",")
        if ext.strip()
    )

    return {
        "standard": {
            "available": _docling_available(),
            "model": "docling-standard-classical",
            "provider": "docling",
            "cost_per_page": "Free",
            "privacy": "local",
            "speed": "slow",
            "experimental": False,
        },
        "llm_api": {
            "available": llm["available"],
            "provider": llm["provider"],
            "model": llm["model"],
            "cost_per_page": llm_cost,
            "privacy": "external",
            "speed": "medium",
            "experimental": False,
            "conversion_prompt": settings.DOCUMENT_LLM_CONVERSION_PROMPT,
        },
        "upload_limits": {
            "allowed_extensions": allowed_extensions,
            "max_bytes": int(settings.DOCUMENT_UPLOAD_MAX_BYTES),
        },
    }


async def _convert_pdf_with_llm_api(path: Path) -> ConversionResult:
    """High-accuracy PDF conversion via direct HTTP call to an OpenAI-compatible endpoint.

    Renders each PDF page to a PNG image via PyMuPDF at the configured DPI, then
    sends the image as base64 to the configured LLM provider (Gemini or OpenAI)
    with the conversion prompt. Reuses ``DOCUMENT_LLM_CONVERSION_PROMPT``,
    ``DOCUMENT_LLM_CONVERSION_CONCURRENCY``, and
    ``DOCUMENT_LLM_CONVERSION_MAX_RETRIES`` settings.

    The HTTP call is made directly via ``httpx`` with tenacity retry on 429/5xx.
    """
    import fitz
    import httpx
    from tenacity import (
        retry,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
    )

    settings = get_settings()
    provider_info = _resolve_llm_provider()
    if not provider_info["available"]:
        raise ValueError(
            "High-accuracy AI conversion requires a configured LLM provider. "
            "Set up Gemini or OpenAI via Settings or .env."
        )

    url = provider_info["url"]
    api_key = provider_info["api_key"]
    model = provider_info["model"]
    prompt = settings.DOCUMENT_LLM_CONVERSION_PROMPT
    concurrency = settings.DOCUMENT_LLM_CONVERSION_CONCURRENCY
    max_retries = settings.DOCUMENT_LLM_CONVERSION_MAX_RETRIES

    dpi = settings.DOCUMENT_PDF_RENDER_DPI
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    # Render all pages to PNG bytes upfront (bounded by PDF size; 200 DPI keeps
    # each page image ~100-300KB as PNG).
    doc = fitz.open(str(path))
    try:
        page_count = len(doc)
        page_images: list[str] = []
        for i in range(page_count):
            pix = doc[i].get_pixmap(matrix=matrix, alpha=False)
            png_bytes = pix.tobytes("png")
            page_images.append(base64.b64encode(png_bytes).decode("ascii"))
    finally:
        doc.close()

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        stop=stop_after_attempt(max_retries + 1),
        wait=wait_exponential(multiplier=5, min=5, max=120),
        reraise=True,
    )
    async def _convert_page(client: httpx.AsyncClient, img_b64: str) -> str:
        payload = {
            "model": model,
            "max_tokens": 8192,
            "temperature": 0.0,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                        },
                    ],
                }
            ],
        }
        resp = await client.post(url, json=payload, timeout=120)
        status = resp.status_code
        # 429 and 5xx are retried by tenacity (raise HTTPStatusError).
        # 401/403 and other 4xx fail fast (raise ValueError — not retried).
        if status == 429 or 500 <= status < 600:
            resp.raise_for_status()
        if status in (401, 403):
            raise ValueError("API key is invalid or expired. Update it in Settings and try again.")
        if 400 <= status < 500:
            raise ValueError(f"The AI provider returned an error (HTTP {status}). Check the API key and server logs.")
        data = resp.json()
        return _extract_llm_choice_text(data)

    pages: list[str] = []
    warnings: list[str] = []
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(headers=headers) as client:
        sem = asyncio.Semaphore(concurrency)

        async def _bounded(img: str) -> str:
            async with sem:
                return await _convert_page(client, img)

        results = await asyncio.gather(
            *(_bounded(img) for img in page_images),
            return_exceptions=True,
        )

    for idx, result in enumerate(results):
        if isinstance(result, Exception):
            logger.warning("llm_api conversion failed on page %d (%s)", idx + 1, type(result).__name__)
            warnings.append(f"Page {idx + 1}: AI conversion failed ({type(result).__name__}). Text may be missing.")
        elif result and result.strip():
            pages.append(result.strip())

    warning = (
        f"Converted with {provider_info['provider']} ({provider_info['model']}). "
        "Review the text if the PDF contains sensitive or complex content."
    )
    warnings.append(warning)
    if not pages:
        warnings.append("No text was extracted from any page. The PDF may be empty or the API may have returned empty responses.")
    return ConversionResult("\n\n---\n\n".join(pages), page_count=page_count, warnings=warnings)


def _extract_llm_choice_text(data: dict[str, Any]) -> str:
    """Extract the text content from an OpenAI-compatible chat completion response."""
    choices = data.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    # Some providers return content as a list of content parts
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(part.get("text", ""))
        return "\n".join(parts)
    return ""


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")
