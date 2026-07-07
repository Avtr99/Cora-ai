# Cora AI Architecture & Open Source Plan

Cora AI has been redesigned from a cloud-dependent (Firebase + Supabase + Qdrant Cloud) architecture into a zero-configuration, self-hosted application optimized for the UN Digital Public Goods registry.

## Target Architecture

The application now runs as a single `docker-compose` stack with the following structure:

```text
cora-ai/
├── frontend/               # Vite React SPA
├── src/                    # FastAPI Backend
│   ├── api/                # REST endpoints (/v1/*)
│   ├── agents/             # RAG orchestration, LLM/Search providers
│   └── db/                 # SQLite configuration and cache
├── data/                   # Persistent Docker volume for SQLite
├── migrations/             # SQLite schema migrations
├── docker-compose.yml      # Local runtime definition
├── Dockerfile              # Multi-stage build (Node -> Python)
├── .env.example            # Template for environment variables
└── README.md               # Setup and execution guide
```

### Runtime Environment
When a user runs `docker-compose up -d --build`:
1. **Container 1 (App)**: 
   - A single Python container runs the FastAPI server.
   - FastAPI serves the compiled React SPA static files at `/`.
   - FastAPI exposes API endpoints under `/v1/`.
   - An SQLite database (`/app/data/cora.db`) is mounted via a persistent volume to store feedback, source requests, and caches.
2. **Container 2 (Qdrant)**:
   - A local Qdrant vector database container runs alongside the app.
   - Vectors are stored in a persistent volume.

## Key Changes & DPG Alignments

### 1. Unified Frontend & Backend
Serving the React app from FastAPI removes a lot of complexity:
- No CORS configuration required for normal use.
- No need for two public URLs or separate hosting services.
- Easier Docker setup and documentation.

### 2. Firebase & Supabase Removal
Firebase and Supabase were removed because they introduced vendor lock-in and Google/Supabase account dependencies.
- `submitFeedback` was ported to FastAPI (`POST /v1/feedback`).
- Persistence for this endpoint and the L2 Cache is now handled by local **SQLite**.

### 3. SQLite Concurrency Optimizations
SQLite is the default for simple self-hosting. To ensure it handles concurrency well:
- Enabled WAL mode (`PRAGMA journal_mode=WAL`).
- Set a busy timeout (`PRAGMA busy_timeout=5000`).
- Database write operations use `run_in_threadpool` to prevent blocking the async FastAPI event loop.

### 4. Pluggable Search & LLM Interfaces
To adhere to DPG standards ("minimal proprietary dependencies"), the architecture introduces interfaces for external APIs:
- **SearchProvider**: Currently defaults to Tavily, with seams to add fully local alternatives like SearXNG.
- **LLMProvider**: Currently defaults to Gemini, with seams to add OpenAI-compatible base URLs for local inference (e.g., Ollama, vLLM).
- **EmbeddingProvider**: Pluggable via `EMBEDDING_PROVIDER` env var — supports Voyage AI, Cohere, Ollama (local), and OpenAI. Defaults to Voyage.
- **RerankerProvider**: Pluggable via `RERANK_PROVIDER` env var — supports Voyage, Cohere, or none. Defaults to Voyage.
- **Citations**: Citations are no longer reliant on Gemini's specific Google Search Grounding. The backend assigns stable IDs to search results (e.g., `[source_1]`), instructs the LLM to cite them, and uses Regex server-side to validate citations and prevent hallucinations.

## Privacy and Data Flow

Transparency is key for open-source and DPG alignment:
- **Stored Locally**: User feedback, source requests, application cache, and vector embeddings are stored entirely locally on the host machine.
- **Sent Externally**: 
  - User messages and conversation context are sent to the configured LLM provider.
  - Search queries are sent to the configured search provider.

## Roadmap & Next Steps
- Implement `SearXNG` and `Ollama` provider classes to offer a 100% offline, local-only operational mode.
- Build basic admin UI routes to view SQLite feedback and source requests.