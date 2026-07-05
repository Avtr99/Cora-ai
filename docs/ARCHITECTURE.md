# Cora AI — Local-First Architecture

> A self-hostable, local-first multi-agent RAG system for the Voluntary Carbon Market (VCM) domain.
> This document describes the **local deployment architecture** after the cloud-hosting remnants
> were removed. It is the canonical reference for how the system runs on a single host.

---

## 1. Design Principles

| Principle | What it means in practice |
|---|---|
| **Local-first** | All persistent state lives on the host filesystem (SQLite + local Qdrant). No managed cloud databases, no cloud vector stores, no cloud analytics. |
| **Single-process deployable** | One FastAPI process serves the API, the React SPA, and the async job queue. Qdrant runs as a sibling container (or a local binary). |
| **Pluggable providers** | Embeddings, reranker, and web search are swappable via env vars. Defaults use hosted APIs (Voyage/Tavily/Gemini), but `ollama` + `none` enable a fully offline stack. |
| **No vendor lock-in for state** | The only required external API key for the default stack is `GEMINI_API_KEY`. Everything else can be replaced with a local provider or disabled. |
| **Read-only at query time** | Ingestion is an offline, out-of-process step. The running container never writes to Qdrant collections during query serving. |

---

## 2. System Topology (Local Docker Stack)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Host Machine                                │
│                                                                     │
│   ┌─────────────────────────┐      ┌─────────────────────────────┐  │
│   │  docker-compose: app    │      │  docker-compose: qdrant     │  │
│   │  (FastAPI + React SPA)  │      │  qdrant/qdrant:v1.18.2      │  │
│   │                         │      │                             │  │
│   │  :8000  HTTP + SPA      │      │  :6333  HTTP/gRPC           │  │
│   │   ├─ /v1/*  API routes  │─────▶│  (vector + memory store)    │  │
│   │   ├─ /api/* SPA aliases │      │                             │  │
│   │   └─ /*     static SPA  │      │  Volume: qdrant_data        │  │
│   │                         │      └─────────────────────────────┘  │
│   │  Volume: cora_data      │                                       │
│   │   └─ /app/data/         │                                       │
│   │       ├─ cora.db        │  ← SQLite (cache, feedback, embeddings)│
│   │       └─ documents/     │  ← uploaded/converted docs            │
│   └─────────────────────────┘                                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
            │
            │  Outbound API calls (configurable, pluggable)
            ▼
   ┌────────────────┬────────────────┬────────────────┐
   │  Gemini API    │  Voyage API    │  Tavily API    │
   │  (LLM)         │  (embed/rerank)│  (web search)  │
   └────────────────┴────────────────┴────────────────┘
```

### 2.1 Two ways to run locally

| Mode | Command | When to use |
|---|---|---|
| **Docker Compose (recommended)** | `docker-compose up -d --build` | Full stack including Qdrant. Production-equivalent. |
| **Native Python** | `python -m src.api.main` | Development. Requires a separately-running Qdrant (set `QDRANT_URL=http://localhost:6333`). |

In native mode, the frontend dev server can run separately with `cd frontend && npm run dev` (Vite on `:8080`); CORS already allows it.

---

## 3. Process & Component Layout

The `app` container runs a **single Python process** (`python -m src.api.main`) that hosts:

1. **The FastAPI HTTP server** (uvicorn) on `:8000`
2. **The built React SPA** served as static files from `frontend/dist`
3. **The async query job queue** (in-process workers, not a separate Celery/Redis broker)
4. **The lifespan initializer** that lazily builds all singletons

### 3.1 Singleton lifecycle (`src/api/lifespan.py`)

All heavy components are constructed **after** the server starts accepting connections, so health probes (`/health`) respond immediately even if a provider is unreachable. The `/ready` endpoint flips to `200` only when `initialization_complete == True`.

```
startup
  ├─ run_migrations()              ← SQLite schema (synchronous, blocking)
  ├─ initialize_components()       ← async background task
  │    ├─ LangChainRetriever       ← connects to Qdrant
  │    ├─ GeminiClient             ← validates API key lazily
  │    ├─ StreamingRAGOrchestrator ← wires retriever + gemini + config
  │    ├─ CitationManager
  │    ├─ AsyncQueryJobManager     ← starts N worker tasks
  │    └─ warmup_connections()     ← pre-warms Qdrant, Gemini, schema discovery, SQLite
  └─ /ready becomes 200 once initialization_complete
```

Access in request handlers is via the module-level globals `retriever`, `gemini_client`, `rag_orchestrator`, `citation_manager` — **not** via FastAPI's `Depends`. This is intentional: the lifespan owns them, and handlers read the globals.

---

## 4. Request Flow

### 4.1 Synchronous query — `POST /v1/query`

```
Client
  │  POST /v1/query  { text, conversation_id?, include_debug? }
  ▼
FastAPI middleware stack:
  CORS → SecurityHeaders → Logging → RequestSizeLimit (5 MB)
  │
  ▼
query_routes.process_query_core
  ├─ Verify SECRET_KEY (history HMAC) — auto-generated on first run if not set in .env
  ├─ Assemble chat history from memory store
  ├─ StreamingRAGOrchestrator.run()
  │     ├─ QueryRewriter      (local acronym expand OR Gemini Lite)
  │     ├─ Router             (regex → year check → keyword count → optional LLM fallback)
  │     ├─ RouteProcessor     (KB | Web | Hybrid | Conversational)
  │     │     ├─ KB:        dense retrieve → rerank → Gemini answer
  │     │     ├─ Web:       Tavily search → Gemini answer + citation validation
  │     │     ├─ Hybrid:    KB first, web fallback on low confidence
  │     │     └─ Conversational: short-circuit, no RAG
  │     └─ Validator (optional, off by default — adds latency)
  ├─ CitationManager.extract()
  ├─ SQLite cache write (backend_cache table, 24h TTL)
  └─ Return JSON { answer, citations, reasoning_steps, ... }
```

### 4.2 Streaming query — `POST /v1/query/stream`

Same pipeline, but the orchestrator emits `AgentStep` events as Server-Sent Events. The frontend `ChatInterface` renders `reasoning_steps` progressively. The orchestrator's `RAG_TIMEOUT_MS` (45s) is enforced via `asyncio` cancellation.

**Token suppression (`tokens` query param):** Clients can pass `?tokens=false` to suppress `token` and `replace` SSE events — only `status`, `result`, `done`, and `error` events are emitted. The orchestrator still runs the full pipeline (including streaming LLM generation internally) but doesn't forward token chunks. This is used by the web UI, which renders the complete answer on the `result` event rather than streaming tokens. Default is `tokens=true` (backward compatible — other API clients using token streaming are unaffected). When `tokens=false`, the KB handler also skips the non-answer buffer gate (no need to hold tokens for inspection when they won't be emitted), reducing latency by ~200-400ms.

### 4.3 Async query — `POST /v1/query/async` + `GET /v1/query/async/{job_id}`

For long-running queries. Returns a `job_id` immediately; an in-process worker (default `ASYNC_QUERY_WORKERS=1`) executes the same `process_query_core` and stores the result in an in-memory job table keyed by `job_id`. Jobs expire after `ASYNC_QUERY_JOB_TTL_SECONDS` (1h). **No external broker** — the queue is in-process and lost on restart.

---

## 5. Data Stores

### 5.1 SQLite (`data/cora.db`)

The single local relational store. Schema is created by `migrations/001_initial.sql` on startup.

| Table | Purpose | Written by | Read by |
|---|---|---|---|
| `schema_migrations` | Migration tracking | `run_migrations()` | `run_migrations()` |
| `feedback` | User thumbs up/down on answers | `POST /v1/feedback` | Operator-only (manual SQLite query) |
| `backend_cache` | Persistent query cache (24h TTL) | `process_query_core` on cache miss | `process_query_core` on every query |
| `embedding_cache` | Durable embedding cache (avoids re-paying for embeddings on restart) | Ingestion + retriever | Retriever |

> **Note on `feedback`:** This is a **write-only collection sink**. There is no read-back endpoint, no UI to view submissions, and no wiring into retrieval or answer generation. The operator reviews it by querying `cora.db` directly. If no one reviews it, the widget is dead weight.

### 5.2 Qdrant (local container, no API key)

Three collections, all on the same Qdrant instance:

| Collection | Purpose | Dimension | Written by |
|---|---|---|---|
| `cora_dense_only` (default name) | Document vectors for RAG retrieval | `EMBEDDING_DIM` (1024 default) | **Ingestion only** (offline) |
| `cora_memories` | Conversation memory vectors | `EMBEDDING_DIM` | Memory API at runtime |
| `vcm_doc_registry` | Document metadata registry | — | Ingestion |

The running `app` container is **read-only** for `cora_dense_only` — it never upserts document vectors during query serving. Only `cora_memories` is written at runtime (via the memory API).

### 5.3 Filesystem (`data/documents/`)

```
data/documents/
  ├─ originals/     ← uploaded files as-received
  ├─ converted/     ← normalized text/markdown after document_loader
  └─ metadata/      ← per-document JSON sidecars
```

Served by the document-store API (`/v1/documents/*` and `/api/documents/*` for the SPA). Path traversal is blocked by `ALLOWED_DOCUMENT_DIRS` validation.

---

## 6. Caching (Single-Tier SQLite, Local-First)

Query result caching is backed by SQLite (`backend_cache` table). Agent-level in-memory caches (TTLCache/LRUCache in routing, rewrite, and conversational handlers) provide short-lived dedup for rapid-fire requests within a session — they are independent dedup layers, not a separate cache tier.

| Store | Location | Scope | TTL |
|---|---|---|---|
| **Query cache** | SQLite `backend_cache` table | Query results (survives restart) | 24h |
| **Embedding cache** | SQLite `embedding_cache` table | Embedding vectors (survives restart) | — |
| **Routing dedup** | In-memory `TTLCache` (`RoutingHandler`) | Dedups rapid-fire routing decisions | 10 min |
| **Rewrite dedup** | In-memory `TTLCache` (`RewriteHandler`) | Dedups rapid-fire query rewrites | 10 min |
| **Intent dedup** | In-memory `LRUCache` (`ConversationalHandler`) | Caches LLM intent classification | session |

- **Embedding cache** is separate (`embedding_cache` table) and shared between ingestion and query-time retrieval.
- There is **no Redis** and no plan to add one. The SQLite design covers the local single-host case.

---

## 7. Pluggable Providers

All external dependencies are swappable via env vars. The default stack uses hosted APIs; the offline stack uses local services.

| Capability | Default (hosted) | Local/offline option | Env var |
|---|---|---|---|
| LLM | Gemini 2.5 Flash / Flash Lite | — (Gemini is currently the only LLM client) | `GEMINI_MODEL_MAIN`, `GEMINI_MODEL_LITE` |
| Embeddings | Voyage `voyage-4-lite` (1024d) | Ollama `bge-large-en-v1.5` (1024d) | `EMBEDDING_PROVIDER` |
| Reranker | Voyage `rerank-2.5` | `none` (skip reranking) | `RERANK_PROVIDER` |
| Web search | Tavily | `none` (disables web route) | `SEARCH_PROVIDER` |

> **Important:** `EMBEDDING_DIM` **must match** the Qdrant collection's vector size. Changing the embedding model requires re-ingesting the collection. There is no online re-ingestion path.

### 7.1 Required vs. optional API keys

| Key | Required? | When |
|---|---|---|
| `GEMINI_API_KEY` | **Yes** | Always — the only LLM client is Gemini |
| `VOYAGE_API_KEY` | Only if `EMBEDDING_PROVIDER=voyage` or `RERANK_PROVIDER=voyage` | Default stack |
| `TAVILY_API_KEY` | Only if `SEARCH_PROVIDER=tavily` | Default stack |
| `COHERE_API_KEY` | Only if using Cohere for embed/rerank | Optional |
| `OPENAI_API_KEY` | Only if `EMBEDDING_PROVIDER=openai` | Optional |
| `SECRET_KEY` | **Auto-generated** | Signs conversation-history HMAC and anonymizes memory user IDs. Auto-generated on first run and persisted to SQLite. Set in `.env` only for multi-instance deployments that need to share signed history. |
| `JWT_SECRET_KEY` | Only if auth endpoints are used | Optional |

The app **starts successfully with no keys configured** — `/health` works, providers fail lazily on first use. This is by design, so health probes don't depend on external services.

---

## 8. Frontend (React SPA)

- **Stack:** Vite + React + TypeScript + TanStack Query + Zustand + Tailwind
- **Build:** `npm run build` produces `frontend/dist/`, which the Dockerfile copies into the backend image and FastAPI serves as static files.
- **Routing:** Client-side (`react-router`). Pages live in `frontend/src/pages/`.
- **API base:** The SPA calls relative paths (`/v1/...`, `/api/...`); FastAPI mounts the same routers under both prefixes. No separate frontend host is needed in production.

### 8.1 What was removed (post-cleanup)

The following cloud-hosting artifacts were deleted to keep the local stack clean:

- **PostHog analytics** + CookieConsent + TermsOfServicePopup + Legal pages
- **Storybook + Chromatic** (cloud-deployed design-system tooling)
- **Source-request feature** (`SourceRequestModal`, `DataSourcesTable`, `POST /v1/source-requests`, `source_requests` table) — was dead code with no closed loop
- **Qdrant API key / SSL** configuration (local Qdrant needs neither)

The footer now shows only "Research project developed in Germany" — no legal links, no "EU Hosted" badge.

---

## 9. Ingestion (Via Running Server)

Ingestion is served by the document_store router at `POST /v1/documents` and runs as background jobs inside the `app` process. Uploaded files are converted to Markdown, chunked, embedded, and upserted into Qdrant.

```
POST /v1/documents (conversion_mode: standard | llm_api)
  └─ src/document_store/jobs.py        ← background job orchestration
       ├─ converter.py                 ← PDF → Markdown
       │    ├─ standard:  Docling classical pipeline (layout + OCR + tables, non-VLM)
       │    └─ llm_api:   Direct HTTP to OpenAI-compatible endpoint (Gemini 2.5 Flash or GPT-4.1-mini, auto-detected)
       ├─ indexer.py                   ← chunk + embed + Qdrant upsert
       │    ├─ embeddings/             ← configured provider (default Voyage)
       │    └─ QdrantVectorStore       ← batched upsert, deduped by doc_store_id
       └─ storage.py                   ← SQLite document/job records
```

- **Conversion modes:** `standard` (Docling classical, non-VLM pipeline — layout + OCR + table structure, free, CPU, ~1-2s/page on properly provisioned hardware, default for most users), `llm_api` (AI service, high accuracy — requires paid API key, direct HTTP call to OpenAI-compatible endpoint). Power users can point `llm_api` at a local vLLM server via `OPENAI_BASE_URL`.
- **`standard` mode:** Docling's classical pipeline (layout model + RapidOCR + TableFormer in fast mode). No VLM is loaded — formula/picture enrichment are off by default. The `DocumentConverter` is a lifespan-managed lazy singleton (`get_docling_converter()`), built on first conversion so missing Docling never breaks startup. Docker images prebake ~700MB of models (layout 327MB + tableformer 342MB + RapidOCR 30MB) into the image at build time via `scripts/docker/download_docling_models.py` — only the models the standard route needs are included (VLM models like CodeFormulaV2 and picture classifier are skipped, saving ~610MB+). RapidOCR is configured for English (VCM docs are English; Docling's default is Chinese). Override with `DOCLING_ARTIFACTS_PATH` to use custom/newer models. PyMuPDF is no longer used for standard extraction — it remains for `llm_api` page rendering and the scanned-doc detection heuristic. Memory peaks ~2GB; `DOCUMENT_DOCLING_MAX_PAGES` bounds page count. Complex merged-cell/nested VCM tables degrade in Markdown — use `llm_api` for table-heavy docs.
- **Docling A/B benchmark (completed):** Defaults are locked to RapidOCR + fast table mode + OCR on, based on benchmarking against EasyOCR, OnnxTR, Tesseract, and PyMuPDF on VCM methodology documents (VM0001, 23 pages). Key findings:
  - **RapidOCR** won on footprint (232MB engine-only vs 598MB for EasyOCR, 2,163MB for OnnxTR) with within-2% speed of EasyOCR. No PyTorch dependency, no system binaries.
  - **Fast table mode** is 20% faster than accurate (3.39 vs 4.25 s/page) with identical heading/table detection on VCM docs. Both tableformer models ship in the same download, so no disk footprint difference.
  - **OCR adds no value on born-digital VCM PDFs** (identical output with or without), but is kept on as a safety net for scanned pages.
  - **Formula enrichment VLM (CodeFormulaV2)** is not viable: 610MB model + PyTorch, crashes after 10 pages on machines with <4GB free RAM, and produces garbage LaTeX. Formulas are recovered as flattened text via `_recover_flattened_formulas` in `converter.py` instead.
  - **Total disk footprint:** 1,236MB (536MB packages + 700MB models). Full results: `results/docling_benchmark_full/COMPARISON.md`.
- **`llm_api` provider requirements:** Sends one API call per PDF page, so a paid API key is required. If 429 errors occur, upgrade to a paid plan or use `standard` mode. See README.md for the provider comparison table.
- **Concurrency:** `DOCUMENT_LLM_CONVERSION_CONCURRENCY` controls parallel page processing (default 5). Reduces conversion time significantly for large PDFs.
- **Retry:** `tenacity` exponential backoff on the direct HTTP call for 429/5xx resilience (backoff 5s/10s/20s/40s, `DOCUMENT_LLM_CONVERSION_MAX_RETRIES`).
- **Re-ingestion requirement:** Changing `EMBEDDING_PROVIDER` or `EMBEDDING_DIM` requires clearing and re-uploading all documents. There is no online migration path.

---

## 10. Security & Compliance

| Concern | Mechanism |
|---|---|
| **PII redaction** | Forced on in production (`PII_REDACTION_ENABLED=True` is hardcoded when `APP_ENV=production`). Applied before memory storage. |
| **User ID anonymization** | Memory store hashes user IDs via HMAC with `MEMORY_SECRET_KEY` (falls back to `SECRET_KEY`). |
| **History integrity** | Conversation history is HMAC-signed with `SECRET_KEY` (auto-generated on first run if not set in `.env`). |
| **Request size** | Hard limit `MAX_REQUEST_BODY_SIZE_BYTES=5 MB`. |
| **Rate limiting** | **None.** Users bring their own API keys; rate limiting the operator is an anti-feature in a local-first tool. |
| **Path traversal** | Document access is constrained to `ALLOWED_DOCUMENT_DIRS`. |
| **Container user** | The `app` container runs as non-root UID 1000. |

> **Local-only caveat:** `CORS_ORIGINS` defaults to a localhost list. If you expose the server beyond localhost, tighten this list. `SECRET_KEY` is auto-generated per instance — for multi-instance deployments, set a shared key in `.env`.

---

## 11. Reliability & Timeouts

| Layer | Setting | Value |
|---|---|---|
| Orchestrator | `RAG_TIMEOUT_MS` | 45s (hard cancel via `asyncio`) |
| Gemini / embeddings | Circuit breaker | 5 failures → open 30s → 3 successes to close |
| Retries | Only 5xx / transient | 429s fail fast (no retry) |
| Qdrant | `QDRANT_TIMEOUT` | 120s |
| Async jobs | `ASYNC_QUERY_JOB_TTL_SECONDS` | 1h (in-memory, lost on restart) |

Timeout checks happen at three points in the orchestrator: after rewrite/route, after main processing, and before validation. Each check cancels the pipeline if the budget is exhausted.

---

## 12. Configuration Surface

All runtime configuration lives in `src/config.py` as a pydantic-settings `Settings` singleton accessed via `get_settings()`. **Never read env vars directly** — go through the singleton.

- **Source of truth:** `.env` file (see `.env.example` for all keys).
- **Validation:** Field validators enforce positive integers, embedding batch ≤ 128, and production PII-redaction override.
- **Hot reload:** None. Settings are read once at singleton construction. Restart to apply changes.

### 12.1 Key tuning knobs for local setups

| Knob | Default | Tune when |
|---|---|---|
| `EMBEDDING_PROVIDER=ollama` | voyage | You want a fully offline stack |
| `RERANK_PROVIDER=none` | voyage | You want to skip reranking (faster, lower quality) |
| `SEARCH_PROVIDER=none` | tavily | You want to disable the web route entirely |
| `ASYNC_QUERY_WORKERS` | 1 | You want concurrent long-query handling |
| `QDRANT_MAX_CONCURRENCY` | 5 | You're hitting Qdrant connection limits |
| `ENABLE_VALIDATION` | False | You need grounding checks and can tolerate extra latency |
| `DARTBOARD_ROUNDS` | 2 | Set to 1 for single-pass retrieval (faster, less recall) |

---

## 13. Operational Checklist (Local Setup)

```powershell
# 1. Configure environment
copy .env.example .env
#    Fill in: GEMINI_API_KEY (required), VOYAGE_API_KEY, TAVILY_API_KEY
#    (SECRET_KEY is auto-generated on first run — no need to set it)

# 2. Start the stack
docker-compose up -d --build

# 3. Verify health
curl http://127.0.0.1:8000/health    # liveness (always 200)
curl http://127.0.0.1:8000/ready     # readiness (200 once initialized)

# 4. Ingest documents (via running server — UI upload or POST /v1/documents)
curl -X POST http://127.0.0.1:8000/v1/documents \
  -F "file=@/path/to/vcm/documents/methodology.pdf" \
  -F "conversion_mode=standard"

# 5. Query
curl -X POST http://127.0.0.1:8000/v1/query \
  -H "Content-Type: application/json" \
  -d '{"text": "What is the VCM?"}'

# 6. Review feedback (manual — no UI endpoint)
sqlite3 data/cora.db "SELECT rating, comment, created_at FROM feedback ORDER BY created_at DESC LIMIT 20;"
```

---

## 14. What Is Explicitly NOT Part of This Architecture

To prevent scope creep and re-introduction of cloud dependencies, the following are **out of scope** for the local-first deployment:

- **No cloud vector store** (Qdrant Cloud, Pinecone, Weaviate Cloud)
- **No managed relational DB** (Supabase, Firebase, PlanetScale)
- **No cloud analytics** (PostHog, Mixpanel, Amplitude)
- **No external job queue** (Celery + Redis, RQ) — the async queue is in-process
- **No cloud deployment target** (Vercel, Railway, Fly.io) — the target is a single host
- **No online re-ingestion** — embedding model changes require a full re-ingest via the CLI
- **No feedback closed loop** — feedback is collected but does not influence retrieval or generation

If any of these become necessary, they should be introduced as **opt-in add-ons** behind a feature flag, not as replacements for the local-first defaults.
