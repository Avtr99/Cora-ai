# Cora AI Roadmap

This file tracks planned work that has been scoped but not yet scheduled for
implementation. Items move out of this file into the active backlog when they
are picked up. Each entry includes the rationale, scope, and acceptance
criteria so an implementer (human or agent) can pick it up without re-deriving
the design.

## Active Candidates

### Retrieval-aware post-generation relevance judge

**Status:** Completed.
**Owner:** Implemented.
**Target component:** `src/agents/validator.py`, `src/agents/route_processor_utils.py`, `src/agents/orchestrator_config.py`, `src/agents/kb_route_handler.py`, `src/agents/hybrid_route_handler.py`.

#### Implementation

The Layer-4 relevance check is now retrieval-aware:

- `AnswerValidator.check_relevance` accepts `source_chunks` and `source_titles` and passes them into the relevance prompt.
- `route_processor_utils.check_answer_relevance` extracts top-k retrieved chunks from `vector_results` and forwards them to the validator.
- `KBRouteHandler` and `HybridRouteHandler` call `check_answer_relevance` before triggering web supplementation.
- `ENABLE_WEB_SUPPLEMENT_RELEVANCE_CHECK` controls the post-generation relevance check independently of `ENABLE_VALIDATION`.
- `WEB_SUPPLEMENT_RELEVANCE_CONFIDENCE_THRESHOLD` requires high confidence before a relevance failure triggers a web fallback.

#### Acceptance criteria

- [x] Relevance prompt includes top retrieved chunks, not just titles.
- [x] Unit tests cover: on-topic grounded answer (kept KB), off-topic answer (web supplement), answer that mentions entity but does not answer detail (web supplement). See `tests/test_relevance_check.py`.
- [x] Config flag `ENABLE_WEB_SUPPLEMENT_RELEVANCE_CHECK` exists to disable the web-supplement relevance check without disabling grounding validation (`ENABLE_VALIDATION`).
- [x] Wired through `route_processor_utils.check_answer_relevance`, `KBRouteHandler`, and `HybridRouteHandler`.
- [x] End-to-end verification on VM0048 definition, VCS JNR framework, and Article 6 queries shows expected route behavior.

#### Trade-offs

- **Pros:** Fewer false negatives on correct KB answers; fewer false positives from lexical overrides; judge evaluates actual grounding.
- **Cons:** Higher token cost and latency (one extra full-context LLM call per KB/hybrid query); may still produce edge-case errors on ambiguous queries.

#### Related documents

- Implementation and tests: `src/agents/validator.py`, `src/agents/route_processor_utils.py`, `tests/test_relevance_check.py`

---

### Replace Docling with PaddleOCR; remove `local_vlm` mode

**Status:** Planned — not yet scheduled.
**Owner:** Unassigned.
**Target component:** `src/document_store/converter.py`, `src/config.py`,
`requirements.txt`, `requirements-ingestion.txt`, `Dockerfile`,
`docker-compose.yml`, frontend upload UI.

#### Rationale

The current ingestion pipeline has two PDF conversion modes:

1. **`standard`** — Docling classical pipeline with OCR and table structure enabled
   (`DOCUMENT_DOCLING_DO_OCR=True`, `DOCUMENT_DOCLING_DO_TABLES=True`, fast
   TableFormer mode). It preserves headings, tables, and reading order locally
   on CPU. Formula/picture enrichment remains off by default
   (`DOCUMENT_DOCLING_DO_FORMULAS=False`).
2. **`llm_api`** — Direct HTTP to an OpenAI-compatible endpoint (Gemini,
   OpenAI, OpenRouter, or a local vLLM server). High accuracy on complex
   layouts, images, and formulas; requires a paid API key or a self-hosted VLM.

The legacy **`local_vlm`** mode has already been removed from the codebase.
Attempting to use it raises a `ValueError` directing users to `standard` or
`llm_api` instead.

Only the `standard` mode depends on Docling. The `llm_api` mode communicates directly with its configured OpenAI-compatible endpoint and does not use Docling. Docling's OmniDocBench performance is
the **worst in the entire benchmark** — Edit distance 0.589 (EN) / 0.909 (ZH),
4x worse than PP-StructureV3 (0.145 / 0.206) and worse than every other
pipeline tool and most VLMs tested.

**PaddleOCR PP-StructureV3** (PaddlePaddle/Baidu, Apache 2.0) is the
replacement for the `standard` pipeline. It is a classical multi-model
document parsing pipeline (all models <100M params combined) that runs on
CPU and produces structured Markdown with headings, tables, formulas, and
reading order. It is the SOTA pipeline tool on OmniDocBench, beating MinerU,
Mathpix, Marker, and Docling.

The result is a **2-tier system** (after the migration):

| Tier | Engine | Hardware | When |
|---|---|---|---|
| 1 (default) | PyMuPDF (born-digital) or PP-StructureV3 (scanned) | CPU only | Most VCM documents |
| 2 (fallback) | `llm_api` (Gemini / OpenAI / local vLLM) | Any + API key or GPU | Reports with images, complex tables, formulas |

`local_vlm` has already been removed. Users who want a local VLM (e.g.
PaddleOCR-VL-1.6, 0.9B params, 2.1GB VRAM) can point `llm_api` at a local
vLLM server via the AI Model settings or `OPENAI_BASE_URL` — a config change,
not a code mode.

#### Accuracy comparison (OmniDocBench, independent — PaddleOCR 3.0 technical report)

| Tool | Edit Distance (EN↓) | Edit Distance (ZH↓) | Type |
|---|---|---|---|
| **PP-StructureV3** | **0.145** | **0.206** | Pipeline (<100M params) |
| Gemini 2.5 Pro | 0.148 | 0.212 | General VLM |
| MinerU 1.3.11 | 0.166 | 0.310 | Pipeline |
| Mathpix | 0.191 | 0.365 | Pipeline |
| Gemini 2.0 Flash | 0.191 | 0.264 | General VLM |
| GOT-OCR2.0 | 0.287 | 0.411 | Expert VLM |
| SmolDocling-256M | 0.493 | 0.816 | Expert VLM |
| **Docling 2.14** | **0.589** | **0.909** | Pipeline |

PP-StructureV3 is 4x more accurate than Docling on English, 4.4x on Chinese.
It beats every pipeline tool and every expert VLM. It is competitive with
Gemini 2.5 Pro — a general VLM that costs money per page.

#### PP-StructureV3 architecture (from PaddleOCR 3.0 technical report)

PP-StructureV3 is a 7-module pipeline:

1. **Preprocessing** — document orientation classification (PP-LCNet) +
   image unwarping (UVDoc)
2. **OCR** — PP-OCRv5/v6 text detection + recognition (50 languages, one model)
3. **Layout detection** — PP-DocLayout (23 categories: text, title, table,
   image, formula, chart, seal, footnote, header, footer, etc.)
4. **Region detection** — separates multiple articles on a single page
   (critical for multi-column magazine/newspaper layouts)
5. **Document item recognition:**
   - **PP-TableMagic** — table structure recovery (wired + wireless tables,
     orientation classification, cell detection, HTML structure output)
   - **PP-FormulaNet** — formula recognition → LaTeX
   - **PP-Chart2Table** — chart parsing → markdown table (lightweight VLM)
   - **PP-OCRv4_seal** — seal/stamp recognition
6. **Post-processing** — reading order recovery (improved X-Y Cut),
   figure/table caption linking
7. **Output** — Markdown / JSON / DOCX

All models combined are <100M parameters. First-run download is ~150MB.

#### Dependency footprint comparison

| | Docling (current) | PaddleOCR (proposed) |
|---|---|---|
| Core package | `docling>=2.0,<3.0` | `paddleocr[doc-parser]>=3.7.0,<4.0` |
| ML framework | PyTorch (~2GB wheel, transitive) | PaddlePaddle CPU (~400MB wheel) |
| Framework install | `pip install docling` (pulls torch) | `pip install paddlepaddle paddleocr[doc-parser]` |
| Core deps | 8 packages (~50MB) + PyTorch + torchvision + accelerate + huggingface_hub + docling-ibm-models | 5 packages (paddlex, PyYAML, requests, aiohttp, typing-extensions) + PaddlePaddle |
| Total install (CPU) | ~2.5GB | ~500MB |
| Total install (GPU) | ~3.5GB | ~1.8GB |
| Model downloads (first run) | ~500MB | ~150MB |
| License | MIT | Apache 2.0 |

#### Code complexity comparison

| | Current (Docling) | Proposed (PaddleOCR) |
|---|---|---|
| converter.py lines | ~607 | ~200 (estimated) |
| Conversion modes | 2 (`standard`, `llm_api`) | 2 |
| Docling-specific functions | 10 | 0 |
| VLM-specific functions | 0 | 0 |
| Platform branching (MLX/CUDA/CPU) | Yes | No (PaddlePaddle auto-detects) |
| Retry session patching | Yes (patches Docling internals) | No |
| pypdfium2 fallback | No | No (PP-StructureV3 is lightweight) |

#### Functions expected to be removed/rewritten in converter.py

Current Docling-specific helpers that would be replaced:

- `_convert_pdf_with_docling_standard` (standard-mode Docling PDF conversion)
- `_docling_available` (Docling import/availability check)
- `_recover_flattened_formulas` (kept only if PP-StructureV3 formula recovery is insufficient)
- `_resolve_llm_provider` / `_extract_llm_choice_text` (kept for `llm_api` mode)
- Any remaining Docling converter setup and markdown-extraction helpers

The `llm_api` mode (`_convert_pdf_with_llm_api`) stays as the fallback tier and is
not Docling-dependent.

#### Architectural principle

**2-tier system. No `local_vlm`. No Docling. No vLLM sidecar. No GPU
requirement for the default tier.**

The `standard` mode becomes a smart router:
- Born-digital PDFs (with embedded text) → PyMuPDF text extraction (instant,
  perfect accuracy, no OCR needed)
- Scanned/image-only PDFs → PaddleOCR PP-StructureV3 (CPU, ~1-2s/page,
  structured markdown with tables, formulas, reading order)

The `llm_api` mode stays for complex documents (images, difficult tables,
formulas) and already calls the OpenAI-compatible API directly via `httpx` —
it does not use Docling.

#### Scope

**In scope:**

1. New `_convert_pdf_with_pymupdf_text()` function (~20 lines):
   - Opens PDF with PyMuPDF (`fitz`).
   - Extracts text per page via `page.get_text("text")`.
   - Preserves page breaks as `\n\n---\n\n` separators.
   - Returns a `ConversionResult` with page count.
   - Used for born-digital PDFs with a detectable text layer.
2. New `_has_text_layer()` helper (~10 lines):
   - Opens PDF with PyMuPDF.
   - Checks if pages have extractable text (sample first 3 pages).
   - Returns `True` if text density > threshold (e.g. 50 chars/page).
3. New `_convert_pdf_with_paddleocr()` function (~80 lines):
   - Renders PDF pages to images via PyMuPDF at 200 DPI.
   - Calls `PPStructureV3().predict()` on each page image.
   - Collects `res.save_to_markdown()` output per page.
   - Concatenates per-page markdown into a single document.
   - Returns a `ConversionResult` with page count and warnings.
   - Configurable: `use_table_recognition=True`, `use_formula_recognition=True`,
     `use_chart_parsing=True`, `lang="en"`.
4. New `_convert_pdf_with_llm_api()` function (~60 lines):
   - Replaces the current Docling-based `_convert_pdf_with_llm`.
   - Renders PDF pages to PNG via PyMuPDF at 200 DPI.
   - Calls the OpenAI-compatible endpoint (`OPENAI_BASE_URL` +
     `/v1/chat/completions`) with page images as base64 + the existing
     `DOCUMENT_LLM_CONVERSION_PROMPT`.
   - Uses `httpx.AsyncClient` with retry on 429/5xx (reuse existing
     `tenacity` pattern from `gemini_client.py`).
   - Reassembles per-page markdown into a single document.
   - Returns a `ConversionResult` with page count and warnings.
5. Update `_convert_pdf()` dispatcher:
   - `standard` mode: if `_has_text_layer(pdf)` → `_convert_pdf_with_pymupdf_text()`,
     else → `_convert_pdf_with_paddleocr()`.
   - `llm_api` mode: `_convert_pdf_with_llm_api()` (direct HTTP, no Docling).
   - `local_vlm` mode: **removed**. Raise `ValueError` if requested.
6. Remove all Docling-specific code (13 functions listed above).
7. Remove all Docling imports from converter.py.
8. Update `get_conversion_capabilities()`:
   - Remove `local_vlm` from the returned dict.
   - `standard` reports: `model: "paddleocr-pp-structurev3"`,
     `provider: "paddleocr"`, `available: True` (always, CPU-only).
   - `llm_api` reports: `model: "gemini-2.5-flash"` (or configured),
     `provider: "openai-compatible"`, `available: bool` based on API key.
9. Remove settings from `src/config.py`:
   - `DOCUMENT_ENABLE_LOCAL_VLM`
   - `DOCUMENT_LOCAL_VLM_*` (all vars)
   - Keep `DOCUMENT_LLM_CONVERSION_*` settings (used by new `llm_api` path).
10. Update `requirements.txt`:
    - Remove `docling>=2.0,<3.0`.
    - Add `paddlepaddle>=3.0.0,<4.0` (CPU wheel — no GPU required).
    - Add `paddleocr[doc-parser]>=3.7.0,<4.0`.
    - Add `pymupdf>=1.24.0,<2.0` explicitly (was transitive via Docling).
    - Keep `httpx` (already present, used by new `llm_api` HTTP path).
11. Update `requirements-ingestion.txt`:
    - Remove `docling>=2.0,<3.0`.
    - Add `paddlepaddle`, `paddleocr[doc-parser]`, `pymupdf`.
12. Update `Dockerfile`:
    - Remove Docling install step.
    - Add PaddlePaddle CPU + paddleocr[doc-parser] install step.
    - PaddlePaddle CPU wheel is ~400MB — smaller than the PyTorch wheel
      Docling was pulling.
13. Update `docker-compose.yml`:
    - Remove the `local-vlm` profile (if it exists).
    - No GPU service needed. The default stack is CPU-only.
14. Update `.env.example`:
    - Remove `DOCUMENT_ENABLE_LOCAL_VLM` and all `DOCUMENT_LOCAL_VLM_*` vars.
    - Keep `DOCUMENT_LLM_CONVERSION_*` and `OPENAI_*` / `GEMINI_*` vars.
15. Frontend upload UI:
    - Remove `local_vlm` option (3 options → 2).
    - `standard` label: "Standard (PaddleOCR) — Fast, free, runs on any
      laptop. Best for text-heavy VCM documents."
    - `llm_api` label: "LLM API — Higher accuracy on complex layouts, images,
      and formulas. Requires an API key. ~$0.002/page."
16. Tests:
    - Unit test for `_convert_pdf_with_pymupdf_text` with a born-digital PDF
      fixture.
    - Unit test for `_has_text_layer` with text and image-only PDF fixtures.
    - Unit test for `_convert_pdf_with_paddleocr` with a mocked
      `PPStructureV3` pipeline (mock `predict()` and `save_to_markdown()`).
    - Unit test for `_convert_pdf_with_llm_api` with a mocked HTTP endpoint
      (`respx` or `httpx` mock).
    - Update existing tests that assert Docling usage or `local_vlm` mode.
    - Remove `local_vlm` test fixtures.
17. Docs:
    - `CLAUDE.md`: update ingestion section — 2 modes, PaddleOCR, no Docling.
    - `AGENTS.md`: update ingestion section — 2 modes, PaddleOCR, no Docling.
    - `README.md`: update setup instructions — `paddlepaddle` + `paddleocr`
      instead of `docling`. Add "Power users: local VLM via vLLM" section
      showing how to point `llm_api` at a local vLLM server running
      PaddleOCR-VL-1.6 or any other VLM.
    - `documentation.md`: update converter function docs.

**Out of scope:**

- Supporting Unlimited-OCR, DeepSeek-OCR, or other large VLMs as built-in
  modes. Power users can point `llm_api` at a local vLLM server running any
  OpenAI-compatible VLM via `OPENAI_BASE_URL`. Document this in the README.
- Fine-tuning PP-StructureV3 on VCM documents. Possible future work if table
  accuracy on specific VCM table patterns is insufficient.
- Bounding-box / coordinate output from PP-StructureV3. Markdown output is
  sufficient for the RAG pipeline. JSON output with coordinates is available
  via `save_to_json()` if needed later.
- PaddleOCR-VL-1.6 as a built-in mode. It requires a GPU and vLLM serving —
  not DPG-aligned for the default tier. Available as a power-user config
  via `llm_api` + local vLLM.

#### Implementation notes

- **Born-digital vs scanned detection.** `_has_text_layer()` samples the first
  3 pages and checks text density. Threshold: >50 chars/page average. This is
  a heuristic — some born-digital PDFs have image-only pages (covers, figures)
  mixed with text pages. If the first 3 pages are image-only but later pages
  have text, the heuristic will route to PP-StructureV3, which is fine — it
  handles born-digital text well too (just slower than direct extraction).
- **PP-StructureV3 configuration.** Default config:
  `PPStructureV3(lang="en", use_table_recognition=True, use_formula_recognition=True,
  use_chart_parsing=True, use_seal_recognition=True, device="cpu")`.
  For GPU users, `device="gpu"` can be set via an env var
  `DOCUMENT_PADDLEOCR_DEVICE: str = "cpu"` (default CPU for DPG compatibility).
- **Table-as-image issue.** In testing, PP-StructureV3 sometimes classifies
  tables as images (especially wireless/merged-cell tables). Mitigations:
  - Ensure `use_table_recognition=True` (default).
  - PP-TableMagic includes wired + wireless table structure models.
  - For tables that still render as images, `llm_api` is the explicit fallback.
  - The current `standard` mode produces NO table structure at all
    (`do_table_structure=False`) — PP-StructureV3 producing some tables as
    images is still better than the status quo.
- **Image handling.** PP-StructureV3 preserves images as file links in
  Markdown (`<img src="..." />`). It does not describe image content (it's
  not a VLM). This is correct behavior for the `standard` tier — image
  description is the job of `llm_api` if needed.
- **`llm_api` mode.** The `llm_api` mode calls the OpenAI-compatible endpoint
  directly via `httpx` and does not depend on Docling. The prompt
  (`DOCUMENT_LLM_CONVERSION_PROMPT`), concurrency
  (`DOCUMENT_LLM_CONVERSION_CONCURRENCY`), and retry
  (`DOCUMENT_LLM_CONVERSION_MAX_RETRIES`) settings are reused unchanged.
- **PaddlePaddle + PyTorch coexistence.** PaddlePaddle and PyTorch can
  coexist in the same Python environment. No conflict. The Cora backend
  uses PyTorch for nothing else after Docling is removed — but if future
  features need PyTorch, both frameworks work together.
- **PaddlePaddle on Windows.** PaddlePaddle supports Windows (including
  RTX 50 series with special wheels). Test on Windows before release.
  The CPU wheel works on all platforms.
- **First-run model download.** PP-StructureV3 downloads ~150MB of models
  on first use. Cached in `~/.paddlex/` (or container volume). Document
  this in setup instructions.
- **PDF rendering.** Use PyMuPDF (`fitz`) at 200 DPI for PP-StructureV3
  input. Higher DPI improves OCR accuracy but increases processing time.
  Make DPI configurable via `DOCUMENT_PADDLEOCR_RENDER_DPI: int = 200`.

#### Acceptance criteria

- [ ] `standard` mode converts a born-digital 50-page VCM PDF via PyMuPDF
      text extraction in under 5 seconds (no OCR, no model loading).
- [ ] `standard` mode converts a scanned 50-page VCM PDF via PP-StructureV3
      on CPU in under 5 minutes.
- [ ] PP-StructureV3 produces structured Markdown with headings, bullet
      lists, and at least some tables in markdown format (manual spot-check
      on 3 representative VCM PDFs from Verra and Gold Standard).
- [ ] `llm_api` mode converts a 50-page VCM PDF via direct HTTP call to
      Gemini/OpenAI without any Docling dependency.
- [ ] `local_vlm` mode is removed — requesting it raises a clear error
      pointing to `standard` or `llm_api`.
- [ ] `/v1/documents/conversion-info` reports only `standard` and `llm_api`,
      with `standard` showing `model: paddleocr-pp-structurev3`,
      `provider: paddleocr`, `available: true`.
- [ ] `docker-compose up -d` works with no GPU, no vLLM, no Docling.
- [ ] `pip install -r requirements.txt` installs without Docling or PyTorch
      (PaddlePaddle CPU wheel only).
- [ ] Frontend upload UI shows 2 options with accurate descriptions.
- [ ] All existing tests updated — no Docling imports, no `local_vlm` tests.
- [ ] New unit tests for PyMuPDF text extraction, PP-StructureV3 (mocked),
      and direct HTTP `llm_api` path all pass.
- [ ] `ruff check src/` clean.
- [ ] `CLAUDE.md`, `AGENTS.md`, `README.md`, `documentation.md` updated.
- [ ] `.env.example` updated — no `DOCUMENT_LOCAL_VLM_*` vars.
- [ ] `Dockerfile` updated — PaddlePaddle CPU + paddleocr, no Docling.

#### Risks

- **Table-as-image classification.** PP-StructureV3 may classify some tables
  as images, especially wireless tables with merged cells. Mitigations:
  `use_table_recognition=True` (default), PP-TableMagic includes wireless
  table models, and `llm_api` is the fallback for documents where table
  structure is critical. Run an internal eval on 5-10 VCM PDFs before
  release to quantify the failure rate.
- **PaddlePaddle framework adoption.** PaddlePaddle is less familiar to
  Western developers than PyTorch. However, the API surface is minimal
  (`PPStructureV3().predict()` → `save_to_markdown()`), and PaddlePaddle
  is a mature framework (2.3M+ developers, Baidu-backed, 84k GitHub stars
  for PaddleOCR). The risk is low — we're using it as a library, not
  training models.
- **PaddlePaddle on Windows.** CPU wheel works on Windows. GPU wheels
  require specific CUDA version matching. Test on Windows before release.
  Default to CPU (`device="cpu"`) for DPG compatibility.
- **First-run model download.** ~150MB download on first PP-StructureV3
  call. Cached in `~/.paddlex/`. Document the one-time delay in setup
  instructions. In Docker, cache via a volume.
- **PP-StructureV3 speed on CPU.** Estimated ~1-2s/page with Mobile OCR
  mode. For a 50-page PDF, that's ~1-2 minutes — acceptable for ingestion.
  Users with GPUs can set `DOCUMENT_PADDLEOCR_DEVICE=gpu` for faster
  processing.
- **`llm_api` endpoint compatibility.** The `llm_api` mode uses a direct
  HTTP call to the configured OpenAI-compatible endpoint. Test thoroughly
  with Gemini, OpenAI, OpenRouter, and local vLLM endpoints, as the image
  encoding and request structure may differ. Run a side-by-side comparison on
  5 PDFs before release.
- **PP-StructureV3 OmniDocBench score is from PaddleOCR's own technical
  report.** The 0.145 EN edit distance is vendor-reported but measured on
  the standard OmniDocBench benchmark. The independent OmniDocBench
  leaderboard shows PaddleOCR-VL-1.5 at 94.93 overall — consistent with
  the technical report's claims for PP-StructureV3 being SOTA among
  pipeline tools.

#### Future work (not in this milestone)

- **PaddleOCR-VL-1.6 as a power-user option.** Document how to run
  `vllm serve PaddlePaddle/PaddleOCR-VL-1.6` and point `llm_api` at it via
  `OPENAI_BASE_URL=http://localhost:8001/v1`. This gives GPU users a local
  high-accuracy VLM without adding a code mode. Add to README as an
  advanced configuration section.
- **PP-ChatOCRv4 for key information extraction.** PaddleOCR's
  PP-ChatOCRv4 pipeline extracts structured key-value pairs from documents
  (names, dates, addresses, amounts). Could be used to extract VCM
  metadata (project ID, methodology version, crediting period) during
  ingestion. Separate milestone.
- **Fine-tune PP-StructureV3 on VCM tables.** If the table-as-image issue
  is persistent on VCM-specific table patterns, fine-tune the table
  classification or structure recognition models on a labeled VCM dataset.
  Separate milestone.
- **PaddleOCR.js for browser-based OCR.** PaddleOCR 3.5 released an
  official browser SDK. Could enable client-side OCR for the frontend
  upload UI (preview before server ingestion). Separate milestone.

---

### Add SearXNG and Serper as web search providers

**Status:** Planned — not yet scheduled.
**Owner:** Unassigned.
**Target component:** `src/agents/search_providers.py`, `src/agents/orchestrator.py`,
`src/api/settings_routes/search.py`, `src/api/settings_routes/status.py`,
`src/config.py`, `.env.example`, frontend settings UI.

#### Rationale

Web search currently supports only Tavily (paid API) and `none` (disabled).
Adding two more providers gives operators meaningful choice and strengthens
the local-first philosophy:

1. **SearXNG** — self-hostable, no API key, fully open source. Aligns with
   Cora's local-first design: an operator who already runs Qdrant and the
   backend locally can also run their own search metasearch engine with zero
   external dependencies and zero cost.
2. **Serper** — Google results via a simple REST API with a generous free tier
   (2,500 searches/month). A good commercial alternative to Tavily for
   operators who want Google-quality results without self-hosting.

#### Scope

- Create `SearXNGSearchProvider` in `src/agents/searxng_search.py`.
  SearXNG exposes a JSON API (`GET /search?format=json&q=<query>`) on any
  self-hosted instance. Configure via `SEARXNG_URL` env var.
- Create `SerperSearchProvider` in `src/agents/serper_search.py`.
  Serper uses `POST https://google.serper.dev/search` with an API key header.
  Configure via `SERPER_API_KEY` env var.
- Update `SEARCH_PROVIDER` valid values in:
  - `src/agents/orchestrator.py` — add `elif` branches for `searxng` and `serper`.
  - `src/api/settings_routes/search.py` — add to `valid_providers` tuple.
  - `src/api/settings_routes/status.py` — add config checks for each provider.
- Update `.env.example` with `SEARXNG_URL` and `SERPER_API_KEY` examples.
- Update frontend settings UI to show the new providers in the dropdown.
- Update README provider configuration section.

#### Acceptance criteria

- [ ] `SEARCH_PROVIDER=searxng` with `SEARXNG_URL=http://localhost:8080`
      returns search results from a local SearXNG instance.
- [ ] `SEARCH_PROVIDER=serper` with `SERPER_API_KEY=<key>` returns Google
      results.
- [ ] `SEARCH_PROVIDER=none` still disables web search (unchanged).
- [ ] `SEARCH_PROVIDER=tavily` still works (unchanged).
- [ ] Unknown provider falls back to a clear error, not a silent default.
- [ ] `/v1/settings/status` reports correct `search_ready` for each provider.
- [ ] `.env.example` and README updated.
- [ ] `ruff check src/` clean.
