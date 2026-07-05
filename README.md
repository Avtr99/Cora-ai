# Cora AI

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](./LICENSE)
[![CI](https://github.com/Avtr99/Cora-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/Avtr99/Cora-ai/actions/workflows/ci.yml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/Avtr99/Cora-ai/badge)](https://scorecard.dev/viewer/?platform=github.com&org=Avtr99&repo=Cora-ai)
<!-- OpenSSF Best Practices baseline badge — detected by Scorecard's CII-Best-Practices check.
     Project page: https://www.bestpractices.dev/projects/13501 -->
[![OpenSSF Baseline](https://www.bestpractices.dev/projects/13501/baseline)](https://www.bestpractices.dev/projects/13501)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![SDG 13](https://img.shields.io/badge/SDG%2013-Climate%20Action-3F7E44)](https://sdgs.un.org/goals/goal13)
[![SDG 4](https://img.shields.io/badge/SDG%204-Quality%20Education-C5192D)](https://sdgs.un.org/goals/goal4)

**An educational AI assistant for the Voluntary Carbon Market (VCM).**

Cora simplifies complex topics on methodologies, pricing, and policies to reduce the
information gap in the voluntary carbon markets. It translates dense registry documents,
standards, methodologies, and project details into clear, accessible language — improving
market transparency and helping users build credible, well-grounded understanding of carbon
credits.

Cora answers questions grounded in your own documents and cites its sources. It is built for
institutional settings where trust, provenance, and data sovereignty matter: all persistent
state lives locally (SQLite + Qdrant), and every external dependency (LLM, embeddings,
reranker, web search) is **pluggable and swappable** — no vendor lock-in.

Cora is designed as an open-source **Digital Public Good**: it runs entirely offline if
needed, owns its data, and can be adapted to any document domain beyond the VCM.

---

## For AI coding agents

If you are an AI agent (Claude Code, Cursor, Devin, etc.) working in this repo, start here:

> Read this README and `.env.example` for full configuration. Setup: copy `.env.example`
> → `.env` and fill in keys; start the stack with `docker-compose up -d --build` (includes
> Qdrant) or run `python -m src.api.main` after starting Qdrant on `localhost:6333`. Build
> the frontend with `cd frontend && npm run build`. Run tests with `pytest`, lint with
> `ruff check src/`. Access settings via the `get_settings()` singleton — never read env
> vars directly. All providers (LLM, embeddings, reranker, search) are pluggable; do not
> introduce hard cloud dependencies.

---

## Why it matters

The Voluntary Carbon Market is opaque. Methodologies, standards, and project documents are
scattered across registries (Verra, Gold Standard, ACR, CAR, Plan Vivo), each with their own
naming schemes, version histories, and acronyms. Practitioners — analysts, registry staff,
project developers, researchers, and learners — spend hours hunting through PDFs to verify a
claim or understand a methodology.

Cora makes that institutional knowledge searchable and verifiable. Drop in your documents,
build a knowledge base once, and get accurate answers with citations back to the source.

### Sustainable Development Goals alignment

Cora advances two UN Sustainable Development Goals:

- **SDG 13 — Climate Action.** The VCM channels private finance into emission-reduction and
  removal projects. By making carbon-market rules and methodologies easier to navigate, Cora
  lowers the barrier to credible, transparent climate finance and helps more people
  participate accurately in the market.
- **SDG 4 — Quality Education.** Cora is an educational tool anyone can use — from
  first-time learners to experienced practitioners. Users can interrogate primary documents
  in plain language and trace every answer back to its source, building domain literacy
  grounded in real artifacts rather than second-hand summaries.

### Digital Public Goods principles

- **Open source** under the Apache 2.0 License.
- **Local-first & data-sovereign.** No document content leaves your machine unless you opt
  into a cloud LLM. SQLite and Qdrant are the only persistent stores.
- **Pluggable by design.** LLM, embeddings, reranker, and web search are all swappable via
  environment variables or the in-app setup wizard — including fully local, zero-cost
  configurations.
- **Adaptable beyond VCM.** Collection descriptions, registry patterns, and system
  instructions are configurable, so Cora can serve any document domain.

---

## Pluggable architecture

Every external service in Cora is behind a provider interface. You pick the combination that
fits your budget, latency, and sovereignty requirements — from all-cloud to fully offline.

| Layer | Default | Alternatives | Config |
|---|---|---|---|
| **LLM** (answers, routing, rewriting) | Google Gemini (`gemini-2.5-flash`) | OpenAI `gpt-4.1-mini`, OpenRouter (any model), Ollama (local), any OpenAI-compatible endpoint (vLLM, LM Studio). Model name is configurable via `LLM_MODEL_MAIN` / `GEMINI_MODEL_MAIN`. | `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL_MAIN` |
| **Embeddings** | Voyage AI (`voyage-4-lite`, 1024d) | Cohere `embed-v4.0`, OpenAI `text-embedding-3-small`, Ollama (`bge-large-en-v1.5`, `nomic-embed-text`, …). The Voyage 4 series (`voyage-4-large`, `voyage-4`, `voyage-4-lite`, `voyage-4-nano`) shares one embedding space, so you can mix models without re-indexing. | `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `EMBEDDING_DIM` |
| **Reranker** | Voyage AI (`rerank-2.5`) | Cohere rerank models, `none` (skip — fully offline) | `RERANK_PROVIDER`, `RERANK_MODEL` |
| **Web search** | Tavily | `none` (answer only from local documents) | `SEARCH_PROVIDER` |
| **Vector store** | Qdrant (local Docker) | Any Qdrant instance (local or remote) | `QDRANT_URL` |
| **PDF conversion** | Docling classical pipeline (local, CPU) | `llm_api` AI service (Gemini / GPT-4.1-mini / local vLLM) | `DOCUMENT_DEFAULT_CONVERSION_MODE` |

### Example configurations

**Gemini + Voyage + Tavily (default, lowest friction):**
```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=...
VOYAGE_API_KEY=...
TAVILY_API_KEY=...
```

**OpenAI GPT-4.1-mini via OpenRouter (multi-provider routing):**
```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=...
LLM_MODEL_MAIN=openai/gpt-4.1-mini
```
OpenRouter exposes hundreds of models behind one OpenAI-compatible endpoint. Browse the full
catalog at https://openrouter.ai/models — the model slug is the provider-prefixed ID shown
there (e.g. `openai/gpt-4.1-mini`). Model availability changes frequently, so pick a current
slug from the catalog rather than relying on a fixed example.

**Fully offline (no API keys, no data leaves the machine):**
```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=http://localhost:11434/v1      # Ollama
LLM_MODEL_MAIN=llama3.1
EMBEDDING_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING_MODEL=bge-large-en-v1.5
EMBEDDING_DIM=1024
RERANK_PROVIDER=none
SEARCH_PROVIDER=none
```

> **Note:** Changing `EMBEDDING_PROVIDER` or `EMBEDDING_DIM` requires clearing and
> re-ingesting all documents, because the Qdrant collection vector size is fixed at creation.

The LLM provider can also be configured at runtime through the in-app **Setup wizard**
(`/setup`), which writes to SQLite and takes precedence over `.env`. If both Gemini and an
OpenAI-compatible key are configured, Cora automatically falls back to the alternate provider
on 429 / quota errors — no manual intervention required.

### Recommended setup

For most users — especially educational and small-team deployments — start with the default
stack and adjust only when you hit a limit or need offline operation.

| Use case | Recommended | Why |
|---|---|---|
| **General Q&A on text-based VCM PDFs** (methodologies, standards, project docs) | Gemini 2.5 Flash + Voyage `voyage-4-lite` embeddings + Voyage `rerank-2.5` + `standard` Docling ingestion | Gemini 2.5 Flash is the deliberate default — strong quality at low cost with reliable rate limits; Voyage gives strong retrieval quality at low cost; Docling's classical pipeline handles text + tables locally and free. |
| **Complex layouts** (scanned pages, dense charts, formulas, image-heavy reports) | Same as above, but ingest with `llm_api` mode (Gemini 2.5 Flash or GPT-4.1-mini) | The AI conversion service recovers structure that classical OCR misses, at ~$0.002/page. | (Paid API Key recommended)
| **Strict data sovereignty / no external calls** | Ollama LLM + Ollama `bge-large-en-v1.5` embeddings + `RERANK_PROVIDER=none` + `SEARCH_PROVIDER=none` + `standard` Docling ingestion | Nothing leaves the machine. Requires a machine with enough RAM for the chosen model. |
| **Multi-model routing / cost optimization** | OpenRouter as the LLM provider | One API key, one endpoint, hundreds of models — switch models by changing `LLM_MODEL_MAIN` only. |

**Gemini free tier note:** Google AI Studio offers a free tier for Gemini models, but its
rate limits are too low for RAG workloads — document ingestion and multi-turn querying will
hit the limit quickly. Use the free tier only to try a single query or two; for real use
(ingesting documents, building a knowledge base, repeated Q&A) upgrade to a paid tier in
AI Studio or use openrouter or switch to a local Ollama LLM for a no-cost, no-rate-limit alternative.

### Where to get API keys

| Provider | What it powers | Get a key |
|---|---|---|
| Google Gemini | LLM (default) — free tier available | https://aistudio.google.com/apikey |
| Voyage AI | Embeddings + reranker (default) | https://dash.voyageai.com |
| Cohere | Embeddings + reranker (alternative) | https://dashboard.cohere.com |
| OpenAI | LLM + embeddings (alternative) | https://platform.openai.com/api-keys |
| OpenRouter | LLM (multi-provider, one key) | https://openrouter.ai/keys |
| Tavily | Web search (default) | https://app.tavily.com |
| Ollama | Local LLM + embeddings (offline) | https://ollama.com/download (no key needed) |

---

## What it does

- **Grounded Q&A.** Ask natural-language questions and get answers with citations back to
  source documents.
- **Multi-route RAG.** The orchestrator chooses the best path — knowledge base, web search,
  hybrid, or conversational — based on the query.
- **Document ingestion.** Upload PDFs, Markdown, TXT, CSV, or JSON through the UI or API.
  Two conversion modes: `standard` (local Docling pipeline, free, CPU) or `llm_api` (AI
  service, higher accuracy on complex layouts).
- **Conversation memory.** Stores chat history as vectors in Qdrant, with HMAC-hashed user
  IDs and optional PII redaction for GDPR compliance.
- **Streaming & async answers.** Real-time token streaming via SSE, or queued async jobs for
  long-running queries.
- **Citations & provenance.** Every KB answer links back to the source chunk; an HTML
  sanitizer (`nh3`) keeps rendered citations safe.
- **Relevance defense chain.** A four-layer filter (rerank floor → pre-generation gate →
  prompt instruction → post-generation LLM check) prevents confident-but-wrong answers.

---

## Quick start (Docker Compose)

The fastest way to run Cora locally.

> **Note:** The Docker image is built for `linux/amd64` because the Python dependency lockfiles are hashed for the x86_64 platform. On Apple Silicon or other arm64 hosts, Docker will run the image under emulation unless you explicitly build for `linux/amd64`.

### 1. Clone and configure

```bash
git clone <repo-url>
cd cora-ai
cp .env.example .env
```

Edit `.env` and set at least:

```env
GEMINI_API_KEY=your_gemini_api_key
VOYAGE_API_KEY=your_voyage_api_key      # default embedding + rerank provider
TAVILY_API_KEY=your_tavily_api_key      # default web search provider
# SECRET_KEY is auto-generated on first run and persisted to SQLite.
# Set it here only if you want to use your own key.
```

### 2. Start the stack

```bash
docker-compose up -d --build
```

This starts:

- `app` (FastAPI + built React SPA) on http://localhost:8000
- `qdrant` (vector database) on http://localhost:6333

### 3. Verify

```bash
curl http://127.0.0.1:8000/health   # liveness
curl http://127.0.0.1:8000/ready    # readiness once initialized
```

### 4. Open the UI

Go to http://localhost:8000. On first run, the onboarding wizard guides you through LLM
configuration if `.env` is not fully set.

### 5. Ingest documents

Upload PDFs through the **Document Store** page, or use the API:

```bash
curl -X POST http://127.0.0.1:8000/v1/documents \
  -F "file=@/path/to/vcm-methodology.pdf" \
  -F "conversion_mode=standard"
```

### 6. Ask questions

```bash
curl -X POST http://127.0.0.1:8000/v1/query \
  -H "Content-Type: application/json" \
  -d '{"text": "What is the VCM?"}'
```

---

## Manual development setup

Use this when you want to run the backend and frontend separately.

### Backend

Requirements: Python 3.11+, a running Qdrant instance.

```bash
pip install -r requirements.txt           # runtime + ingestion
# or
pip install -r requirements.txt -r requirements-dev.txt  # + tests + RAGAS eval

# Start Qdrant
docker run -d -p 6333:6333 qdrant/qdrant:v1.18.2

# Copy and edit .env
cp .env.example .env
# Set QDRANT_URL=http://localhost:6333 and add your API keys

python -m src.api.main
```

The backend runs on http://localhost:8000.

### Frontend

Requirements: Node.js 22+.

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server runs on http://localhost:8080. CORS is pre-configured for local
development. To build for production, run `npm run build` — FastAPI then serves
`frontend/dist/` as static files.

---

## Architecture

```
User Query
  ↓
QueryRewriter   (expand VCM acronyms, fix typos, resolve coreferences)
  ↓
Router          (regex → year check → keyword count → optional LLM fallback)
  ↓
RouteProcessor  (KB | Web | Hybrid | Conversational)
  ↓
Answer          (configured LLM: Gemini / OpenAI / Ollama / OpenRouter)
  ↓
CitationManager + optional Validator (post-generation relevance check)
```

**Backend:** FastAPI (`src/api`), agents (`src/agents`), retrieval (`src/retrieval`),
LLM clients (`src/query_processing`), embeddings factory (`src/embeddings`),
SQLite cache (`src/db`), conversation memory (`src/memory`), citations (`src/citations`).

**Frontend:** Vite + React 18 + TypeScript + TanStack Query + Zustand + Tailwind CSS.

**Stores:** SQLite (`data/cora.db`) for cache, feedback, embeddings, and app settings;
Qdrant for vectors and conversation memory.

### Route decision flow

- **knowledge_base** — four-layer defense chain (cheapest → most expensive):
  1. *Retrieval:* dense search → rerank → score floor → optional lexical-overlap guard →
     diversification + methodology boosting.
  2. *Pre-generation gate:* if the best doc's rerank score is below
     `KB_MIN_TOP_RELEVANCE_SCORE`, skip KB → web fallback (before any tokens generated).
  3. *Answer generation:* the prompt instructs the model to say "Information not found…"
     if retrieved chunks don't address the question.
  4. *Post-generation check:* `validator.check_relevance(query, answer)` runs
     unconditionally in the sync path — semantic similarity ≠ answer relevance.
- **web_search** — pluggable search provider fetches results, LLM generates an answer with
  citation validation.
- **hybrid** — KB + web retrieval → answer synthesis → post-generation relevance check
  (graceful "couldn't verify" fallback if web is unavailable).
- **conversational** — short-circuit for greetings/chitchat; bypasses the RAG pipeline
  entirely (saves 2–4 LLM calls).

### Reliability

- Global orchestrator timeout: `RAG_TIMEOUT_MS` (45s).
- Circuit breakers on all external API calls (Gemini, embedding provider) with `tenacity`
  exponential backoff. 5xx retried; 429s fail fast.
- Single-tier SQLite query cache (24h TTL, persistent across restarts) plus durable
  embedding cache. Agent-level in-memory caches dedup rapid-fire routing/rewrite calls.

---

## Ingestion modes

### `standard` (default)

- Local, free, CPU-based. No data leaves the machine.
- Docling classical pipeline: layout model + RapidOCR (English) + TableFormer (fast mode).
- ~1–2s/page on properly provisioned hardware. Preserves headings, tables, and reading
  order; OCRs scanned pages. No VLM is loaded.
- Docker images prebake ~700MB of Docling models at build time. For non-Docker setups,
  prefetch with `python scripts/docker/download_docling_models.py ~/.cache/docling/models`
  (or set `DOCLING_ARTIFACTS_PATH`).

### `llm_api`

- AI service (auto-detected: Gemini 2.5 Flash or GPT-4.1-mini via the OpenAI-compatible
  endpoint). Higher accuracy on complex layouts, charts, images, and formulas.
- Requires a paid API key; ~$0.002/page. Tunable concurrency and retry settings.
- Power users can point it at a local vLLM server (e.g. PaddleOCR-VL-1.6) via
  `OPENAI_BASE_URL` — a config change, not a code mode.

---

## API highlights

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness |
| GET | `/ready` | Readiness (components initialized) |
| POST | `/v1/query` | Synchronous RAG query |
| POST | `/v1/query/stream` | Streaming SSE query |
| POST | `/v1/query/async` | Async queued query (returns `job_id`) |
| GET | `/v1/query/async/{job_id}` | Poll async job |
| POST | `/v1/summarize` | Document summarization |
| POST | `/v1/documents` | Upload document |
| GET | `/v1/documents` | List documents |
| GET/POST | `/v1/memory/*` | Conversation memory CRUD |
| GET/POST | `/api/v1/settings/*` | LLM / app settings + setup wizard |
| GET | `/docs` | OpenAPI Swagger UI |

Full interactive docs are available at `/docs` once the server is running.

---

## Configuration

All runtime settings live in `src/config.py` and load from `.env`. See `.env.example` for
every option. The most important ones:

| Variable | Why you need it |
|---|---|
| `LLM_PROVIDER` | `gemini` (default) or `openai_compatible`. |
| `GEMINI_API_KEY` | Required when `LLM_PROVIDER=gemini`. |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL_MAIN` | Required when `LLM_PROVIDER=openai_compatible`. |
| `EMBEDDING_PROVIDER` | `voyage` (default), `cohere`, `ollama`, or `openai`. |
| `RERANK_PROVIDER` | `voyage` (default), `cohere`, or `none`. |
| `SEARCH_PROVIDER` | `tavily` (default) or `none`. |
| `SECRET_KEY` | Signs conversation history and anonymizes memory user IDs. **Auto-generated on first run** and persisted to SQLite — no setup needed. Set it in `.env` only if you want your own key. |

### KB relevance thresholds (tunable, with per-collection overrides)

| Setting | Default | Purpose |
|---|---|---|
| `RERANK_SCORE_THRESHOLD` | 0.2 | Hard rerank floor in the retriever. |
| `KB_MIN_TOP_RELEVANCE_SCORE` | 0.4 | Pre-generation gate; below this → web fallback. |
| `QUERY_DOC_OVERLAP_THRESHOLD` | 0.0 (off) | Zero-cost lexical overlap guard. |
| `COLLECTION_RELEVANCE_OVERRIDES` | — | JSON map of per-collection threshold overrides. |

---

## Contributing

We welcome contributions — bug reports, fixes, new pluggable providers, documentation, and
domain adaptations beyond the VCM. See [CONTRIBUTING.md](CONTRIBUTING.md) for the full
workflow.

A few architecture rules worth highlighting up front:

- **Do not introduce new hard cloud dependencies.** Any new external service must sit behind
  a pluggable provider interface with at least one open-source or local alternative.
- **API endpoints** go under `/v1/`.
- **Database migrations** are added as `.sql` files in `migrations/`.
- Run `ruff check src/` (Python) and `npm run lint` (frontend) before opening a PR.
- Pre-commit hooks (`gitleaks` + `ruff`) must pass — install them with `pre-commit install`.

Fork → branch → PR. Thank you for contributing.

---

## License

Apache License 2.0. See `LICENSE` and `NOTICE`.
