"""Application settings schema with environment-based configuration.

Runtime management (singleton, DB overlay, per-collection thresholds) lives in
``config_store.py``; this module defines only the ``Settings`` schema, its
field validators, and the derived helpers that depend on the schema itself.
Filter-field name normalization lives in ``config_validation.py``.
"""

from pathlib import Path
from typing import Optional, List, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    # --- API keys (optional to allow health-probe startup; validated lazily on use) ---
    GEMINI_API_KEY: Optional[str] = None
    # VOYAGE_API_KEY / COHERE_API_KEY / OPENAI_API_KEY are .env-only fallbacks used
    # by env-provider detection and the LLM profile manager. The embeddings and
    # reranker subsystems read their own scoped keys (below) so saving one in the
    # Settings UI never overwrites the other. See migration 009 and
    # docs/ROADMAP_FRAGILITY_AUDIT.md (P0 shared-key fix).
    VOYAGE_API_KEY: Optional[str] = None  # .env fallback (LLM env detection)
    COHERE_API_KEY: Optional[str] = None  # .env fallback (LLM env detection)
    OPENAI_API_KEY: Optional[str] = None  # .env fallback (LLM env detection)
    OPENROUTER_API_KEY: Optional[str] = None  # OpenRouter multi-provider gateway

    # Scoped API keys — written by the embeddings/reranker Settings UI routes and
    # overlaid on the Settings singleton by config_store._apply_db_overlay. Each
    # subsystem reads only its own key, so the cross-contamination bug (both
    # routes writing the same voyage_api_key/cohere_api_key row) is impossible.
    EMBEDDING_VOYAGE_API_KEY: Optional[str] = None
    EMBEDDING_COHERE_API_KEY: Optional[str] = None
    EMBEDDING_OPENAI_API_KEY: Optional[str] = None
    RERANKER_VOYAGE_API_KEY: Optional[str] = None
    RERANKER_COHERE_API_KEY: Optional[str] = None

    # --- OpenAI-compatible model overrides (optional; defaults are tested recommendations) ---
    # When set, these override the hardcoded defaults used by env-provider detection
    # and the fallback client builder. Users can point OpenRouter at any model the
    # gateway serves (e.g. "openai/gpt-4.1-mini", "anthropic/claude-3.5-sonnet").
    OPENAI_MODEL: Optional[str] = None
    OPENAI_MODEL_LITE: Optional[str] = None
    OPENROUTER_MODEL: Optional[str] = None
    OPENROUTER_MODEL_LITE: Optional[str] = None

    # --- Embedding provider (pluggable: voyage | cohere | ollama | openai) ---
    # EMBEDDING_DIM must match the Qdrant collection vector size; changing it requires re-ingest.
    EMBEDDING_PROVIDER: str = "voyage"
    EMBEDDING_MODEL: str = "voyage-4-lite"
    EMBEDDING_DIM: int = 1024
    # Tuned to stay under Voyage's ~120K tokens/request ceiling with CHUNK_SIZE=1500.
    EMBEDDING_BATCH_SIZE: int = 256
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # --- Reranker provider (pluggable: voyage | cohere | none) ---
    RERANK_PROVIDER: str = "voyage"
    RERANK_MODEL: str = "rerank-2.5"

    # --- LLM models (main for answers, lite for routing/validation) ---
    GEMINI_MODEL_MAIN: str = "gemini-2.5-flash"
    GEMINI_MODEL_LITE: str = "gemini-2.5-flash-lite"

    # --- Qdrant (local Docker; no API key needed) ---
    QDRANT_URL: Optional[str] = None  # Required for vector store, validated on use
    QDRANT_COLLECTION_NAME: str = "cora_dense_only"
    QDRANT_TIMEOUT: int = 120
    # Caps upsert payload size for large PDFs to avoid gRPC/HTTP message limits.
    QDRANT_UPSERT_BATCH_SIZE: int = 1000

    # Comma-separated metadata fields allowed for Qdrant payload filtering.
    # CSV columns are auto-discovered at ingest time when QDRANT_AUTO_INDEX_CSV_COLUMNS=true.
    QDRANT_ALLOWED_FILTER_FIELDS: str = (
        "source,file_type,doc_type,category,registry,standard,publisher,policy_framework,"
        "document_id,version_number,title,methodology_codes,"
        "country,status,program_name,date,methodology_name,reference_id,"
        "chunk_index,source_chunk_index,block_index,json_index"
    )

    # --- Retrieval ---
    MAX_CHUNKS_PER_SOURCE: int = 5  # Post-rerank source diversity cap; 0 disables

    # --- Chunking (indexing-time; see src/document_store/indexer.py) ---
    # A/B test winner (see CLAUDE.md); changing requires re-indexing existing documents.
    CHUNK_SIZE: int = 1500
    CHUNK_OVERLAP: int = 300

    # --- Multi-round retrieval (expansion-pool design; see CLAUDE.md) ---
    # Round 2 only expands the candidate pool before a single rerank pass — it is not a refinement pass.
    DARTBOARD_ROUNDS: int = 2  # 1 = single pass, 2 = expand pool if sparse
    ROUND1_K: int = 15  # Final top-K after reranking
    ROUND1_THRESHOLD: float = 0.3  # Only used when reranking is disabled
    ROUND2_CANDIDATES: int = 30  # Candidates fetched in round 2 to expand the pool
    # Layer 1 of the KB defense chain (see CLAUDE.md). Hard rerank floor; set 0 to disable.
    RERANK_SCORE_THRESHOLD: float = 0.2
    # Layer 2 of the KB defense chain (see CLAUDE.md). Pre-generation gate; set 0 to disable.
    KB_MIN_TOP_RELEVANCE_SCORE: float = 0.4
    # Zero-cost lexical overlap guard (see CLAUDE.md). Set 0 to disable.
    QUERY_DOC_OVERLAP_THRESHOLD: float = 0.0

    # --- Collection-level domain extensibility (VCM remains the default) ---
    # Appended to the default VCM description so non-VCM docs route accurately.
    COLLECTION_DESCRIPTION: Optional[str] = None
    # JSON file path with extra RegistryPattern definitions merged with built-in VCM patterns.
    CUSTOM_REGISTRY_PATTERNS: Optional[str] = None
    # Replaces the default VCM expertise list so the LLM answers without VCM bias.
    COLLECTION_SYSTEM_INSTRUCTION: Optional[str] = None
    # Temporal cutoff for market/pricing data. None means "current year - 1".
    KB_MARKET_DATA_CUTOFF_YEAR: Optional[int] = None
    # Per-collection JSON overrides for relevance thresholds (see config_store.get_collection_threshold).
    COLLECTION_RELEVANCE_OVERRIDES: Optional[str] = None

    # --- Multi-agent RAG feature flags ---
    ENABLE_QUERY_REWRITING: bool = True
    USE_QUICK_REWRITE: bool = True  # Local acronym expansion only (~200ms saved)
    ENABLE_ROUTING: bool = True
    ENABLE_WEB_SEARCH: bool = True  # Required for queries outside the KB
    ENABLE_VALIDATION: bool = False  # Optional grounding check (adds latency)
    # Disables the post-generation web-supplement relevance judge; ENABLE_VALIDATION is separate.
    ENABLE_WEB_SUPPLEMENT_RELEVANCE_CHECK: bool = True
    WEB_SUPPLEMENT_RELEVANCE_CONFIDENCE_THRESHOLD: float = 0.8

    # --- Sub-query fusion retrieval ---
    ENABLE_SUBQUERY_FUSION: bool = True
    SUBQUERY_CANDIDATES: int = 15  # Dense candidates per sub-query (main query uses INITIAL_CANDIDATES)

    # --- Answer generation ---
    MAX_CONTEXT_CHARS: int = 16000
    MAX_DOCUMENTS_FOR_ANSWER: int = 10

    # --- Prompt repetition (RAG accuracy vs cost) ---
    ENABLE_VALIDATOR_PROMPT_REPETITION: bool = True
    PROMPT_REPETITION_CONTEXT_THRESHOLD: Optional[int] = 12000

    # --- Citations ---
    CITATION_MIN_RELEVANCE_SCORE: float = 0.3

    # --- Agent in-memory cache TTLs (dedup rapid-fire duplicates on warm instances) ---
    ROUTE_CACHE_TTL: int = 600
    REWRITE_CACHE_TTL: int = 600

    # --- SQLite persistent cache (survives restarts) ---
    CACHE_ENABLED: bool = True
    CACHE_TTL_SECONDS: int = 86400

    # --- API / server ---
    TIMEOUT: int = 30
    UVICORN_HOST: str = "0.0.0.0"
    PORT: int = 8000
    RAG_TIMEOUT_MS: int = 45000  # End-to-end orchestrator timeout

    # --- Async query jobs (Phase 3) ---
    ASYNC_QUERY_WORKERS: int = 1
    ASYNC_QUERY_QUEUE_MAX_SIZE: int = 100
    ASYNC_QUERY_JOB_TTL_SECONDS: int = 3600

    # --- Security ---
    API_ACCESS_KEY: Optional[str] = None  # Optional key for protected endpoints
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080,http://localhost:8000,http://localhost:5000,http://localhost:5001"
    SECRET_KEY: Optional[str] = None  # Required for history HMAC signing, validated on use
    MEMORY_SECRET_KEY: Optional[str] = None  # Preferred for memory anonymization; falls back to SECRET_KEY
    PII_REDACTION_ENABLED: bool = True  # GDPR compliance before memory storage
    ENABLE_API_KEY_PROTECTION: bool = False
    ENABLE_TEST_ENDPOINT: bool = False  # Dev-only test query endpoint
    MAX_REQUEST_BODY_SIZE_BYTES: int = 5 * 1024 * 1024

    # --- JWT auth ---
    JWT_SECRET_KEY: Optional[str] = None  # Required for auth, validated on use
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --- Logging ---
    LOG_LEVEL: str = "INFO"
    LOG_JSON_FORMAT: bool = False  # Set True for production log aggregators

    # --- Auth controls ---
    ENABLE_INSECURE_TOKEN_ENDPOINT: bool = False  # Dev-only token issuance

    # --- Conversational handler ---
    CONVERSATIONAL_INTENT_CACHE_SIZE: int = 512
    CONVERSATIONAL_INTENT_MAX_TOKENS: int = 5
    CONVERSATIONAL_MAX_OUTPUT_TOKENS: int = 150

    # --- Web search ---
    SEARCH_PROVIDER: str = "tavily"
    TAVILY_API_KEY: Optional[str] = None

    # --- SQLite ---
    DATABASE_URL: str = "sqlite:///data/cora.db"
    # WAL is the default for both local dev and Docker (named volume; see docker-compose.yml).
    SQLITE_JOURNAL_MODE: str = "WAL"

    # --- Document store / uploads ---
    ALLOWED_DOCUMENT_DIRS: str = "./data,./uploads"  # Comma-separated allowed base directories
    DOCUMENT_STORE_ROOT: str = "./data/documents"
    DOCUMENT_UPLOAD_MAX_BYTES: int = 50 * 1024 * 1024
    DOCUMENT_ALLOWED_EXTENSIONS: str = ".pdf,.md,.txt,.csv,.json,.jsonl"
    # Used by `llm_api` mode only; `standard` mode extracts text directly. 200 = accuracy/speed trade-off.
    DOCUMENT_PDF_RENDER_DPI: int = 200
    DOCUMENT_LLM_CONVERSION_PROMPT: str = (
        "Convert this page to clean Markdown for a knowledge base. "
        "Preserve headings, tables, lists, references, and important text. "
        "For images & figures describe them, for mathematical expressions use latex markdown. Return only Markdown."
    )
    # Tenacity backoff on 429/5xx for the direct HTTP call to the OpenAI-compatible endpoint.
    DOCUMENT_LLM_CONVERSION_MAX_RETRIES: int = 4
    # Parallel PDF pages for llm_api conversion. Lower if hitting 429 rate limits.
    DOCUMENT_LLM_CONVERSION_CONCURRENCY: int = 5

    # --- Ingestion concurrency ---
    # Caps simultaneous convert/index jobs; Docling is CPU/RAM-heavy, embeddings are network-bound.
    DOCUMENT_INGESTION_CONCURRENCY: int = 2

    # --- Ingestion dispatch ---
    # "in_process" = FastAPI BackgroundTask (non-Docker). "worker" = separate ingest-worker container.
    INGESTION_DISPATCH: Literal["in_process", "worker"] = "in_process"
    INGEST_WORKER_POLL_INTERVAL_SECONDS: float = 2.0
    INGEST_WORKER_HEARTBEAT_INTERVAL_SECONDS: float = 10.0
    # Must be well under INGEST_WORKER_STALE_SECONDS so is_worker_alive() stays true during long conversions.
    INGEST_WORKER_STALE_SECONDS: float = 30.0
    # Stuck-job sweep cadence (one cheap UPDATE every N polls avoids redundant DB writes).
    INGEST_WORKER_STALE_SWEEP_EVERY_N_POLLS: int = 5
    # Must be > DOCUMENT_JOB_HARD_TIMEOUT_MARGIN_SECONDS so the hard timeout fires before the sweep.
    INGEST_WORKER_STALE_GRACE_SECONDS: float = 180.0

    # --- Docling standard (classical, non-VLM) PDF conversion ---
    # Formula/picture enrichment loads VLMs, so they are OFF by default (opt in via .env).
    DOCUMENT_DOCLING_OCR_ENGINE: str = "rapidocr"  # rapidocr | tesseract | onnxtr | easyocr
    DOCUMENT_DOCLING_DO_OCR: bool = True
    DOCUMENT_DOCLING_DO_TABLES: bool = True
    # "fast" = 20% faster, ~70MB less RAM (see results/docling_benchmark_full/COMPARISON.md).
    DOCUMENT_DOCLING_TABLE_MODE: str = "fast"
    DOCUMENT_DOCLING_DO_FORMULAS: bool = False
    DOCUMENT_DOCLING_MAX_FILE_BYTES: int = 50 * 1024 * 1024
    # Docling returns PARTIAL_SUCCESS past this; we surface a clear timeout error instead of indexing partial docs.
    DOCUMENT_DOCLING_TIMEOUT: float = 1800.0
    # Margin added to DOCUMENT_DOCLING_TIMEOUT for the asyncio.wait_for ceiling over the whole job.
    DOCUMENT_JOB_HARD_TIMEOUT_MARGIN_SECONDS: float = 120.0
    # Pre-downloaded Docling model artifacts. Docker prebakes /app/models/docling at build time.
    DOCLING_ARTIFACTS_PATH: Optional[str] = None

    @property
    def allowed_document_dirs_resolved(self) -> list:
        """Resolved absolute paths for ALLOWED_DOCUMENT_DIRS (relative to cwd)."""
        dirs = [d.strip() for d in self.ALLOWED_DOCUMENT_DIRS.split(",") if d.strip()]
        return [str(Path(d).resolve()) for d in dirs]

    @field_validator(
        "ASYNC_QUERY_WORKERS", "ASYNC_QUERY_QUEUE_MAX_SIZE", "ASYNC_QUERY_JOB_TTL_SECONDS",
        "CONVERSATIONAL_INTENT_CACHE_SIZE", "CONVERSATIONAL_INTENT_MAX_TOKENS",
        "CONVERSATIONAL_MAX_OUTPUT_TOKENS", "SUBQUERY_CANDIDATES",
        "DOCUMENT_INGESTION_CONCURRENCY", "EMBEDDING_BATCH_SIZE",
        "QDRANT_UPSERT_BATCH_SIZE", "INGEST_WORKER_STALE_SWEEP_EVERY_N_POLLS",
        "CHUNK_SIZE", "CHUNK_OVERLAP",
    )
    @classmethod
    def validate_positive_int(cls, v: int, info) -> int:
        """Ensure integer settings are positive."""
        if v <= 0:
            raise ValueError(f"{info.field_name} must be a positive integer")
        return v

    @field_validator("DOCUMENT_LLM_CONVERSION_PROMPT")
    @classmethod
    def validate_conversion_prompt_not_empty(cls, v: str) -> str:
        """Prevent whitespace-only prompts that would degrade VLM conversion quality."""
        if not v or not v.strip():
            raise ValueError("DOCUMENT_LLM_CONVERSION_PROMPT must not be empty or whitespace-only")
        return v

    @field_validator(
        "DOCUMENT_DOCLING_TIMEOUT",
        "DOCUMENT_JOB_HARD_TIMEOUT_MARGIN_SECONDS",
        "INGEST_WORKER_POLL_INTERVAL_SECONDS",
        "INGEST_WORKER_HEARTBEAT_INTERVAL_SECONDS",
        "INGEST_WORKER_STALE_SECONDS",
        "INGEST_WORKER_STALE_GRACE_SECONDS",
    )
    @classmethod
    def validate_positive_timeout(cls, v: float, info) -> float:
        """Ensure timeout/interval settings are positive numbers."""
        if v <= 0:
            raise ValueError(f"{info.field_name} must be a positive number")
        return v

    @field_validator("SQLITE_JOURNAL_MODE")
    @classmethod
    def validate_sqlite_journal_mode(cls, v: str) -> str:
        """Ensure the configured SQLite journal mode is supported."""
        mode = v.upper()
        allowed = {"DELETE", "TRUNCATE", "PERSIST", "MEMORY", "WAL", "OFF"}
        if mode not in allowed:
            raise ValueError(
                f"SQLITE_JOURNAL_MODE must be one of {sorted(allowed)}, got {v!r}"
            )
        return mode

    _validated_filter_fields: Optional[List[str]] = None

    def get_validated_allowed_filter_fields(self) -> List[str]:
        """Sanitized, cached filter fields from QDRANT_ALLOWED_FILTER_FIELDS.

        Splits the comma-separated string, normalizes each name for Qdrant,
        validates characters and length, and caches the result on the instance.

        Raises:
            ValueError: If any configured field contains disallowed characters.
        """
        if self._validated_filter_fields is not None:
            return self._validated_filter_fields

        from .config_validation import normalize_filter_field_name

        validated: List[str] = []
        for raw_field in self.QDRANT_ALLOWED_FILTER_FIELDS.split(","):
            field = raw_field.strip()
            if not field:
                continue
            validated.append(normalize_filter_field_name(field))

        self._validated_filter_fields = validated
        return validated

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore"
    )


# ---------------------------------------------------------------------------
# Runtime management (singleton, DB overlay, per-collection thresholds) lives
# in config_store.py to keep this file focused on the settings schema. Re-export
# the public API so existing `from ..config import get_settings` imports work
# without changes.
# ---------------------------------------------------------------------------
from .config_store import (  # noqa: E402
    get_settings,
    reload_settings,
    reset_settings_singleton,
    get_collection_threshold,
)

__all__ = [
    "Settings",
    "get_settings",
    "reload_settings",
    "reset_settings_singleton",
    "get_collection_threshold",
]
