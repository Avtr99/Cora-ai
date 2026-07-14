"""Application settings schema with environment-based configuration.

Runtime management (singleton, DB overlay, per-collection thresholds) lives in
``config_store.py``; this module defines only the ``Settings`` schema and the
filter-field validation helper.
"""

import logging
import re
from typing import Optional, List

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

logger = logging.getLogger(__name__)

_FILTER_FIELD_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
_FILTER_FIELD_MAX_LENGTH = 64

def normalize_filter_field_name(field: str) -> str:
    """
    Normalize and validate a filter field name for Qdrant compatibility.

    Args:
        field: Raw field name that may include spaces or disallowed chars.

    Returns:
        Normalized field name using underscores.

    Raises:
        ValueError: If the normalized field contains invalid characters or is too long.
    """
    if field is None:
        raise ValueError("Filter field name cannot be None")

    trimmed = field.strip()
    if not trimmed:
        raise ValueError("Filter field name cannot be empty")

    normalized = (
        trimmed.replace(" ", "_")
        .replace("/", "_")
        .replace("-", "_")
    )

    if len(normalized) > _FILTER_FIELD_MAX_LENGTH:
        raise ValueError(
            f"Filter field '{field}' exceeds maximum length of {_FILTER_FIELD_MAX_LENGTH} characters"
        )

    if not _FILTER_FIELD_PATTERN.fullmatch(normalized):
        raise ValueError(
            f"Filter field '{field}' contains disallowed characters "
            "(only letters, numbers, and underscores are permitted)"
        )

    return normalized


class Settings(BaseSettings):
    # API Keys - Made optional to allow app startup for health probes
    # Validation happens lazily when these are actually used
    GEMINI_API_KEY: Optional[str] = None
    VOYAGE_API_KEY: Optional[str] = None  # Required when EMBEDDING_PROVIDER=voyage
    COHERE_API_KEY: Optional[str] = None  # Required when EMBEDDING_PROVIDER=cohere or RERANK_PROVIDER=cohere
    OPENAI_API_KEY: Optional[str] = None  # For OpenAI API access
    OPENROUTER_API_KEY: Optional[str] = None  # For OpenRouter (multi-provider gateway)

    # Embedding Provider Settings (pluggable — no vendor lock-in)
    # Supported: voyage (default), cohere, ollama (local)
    # Dimension must match the Qdrant collection vector size.
    # 1024d-compatible models: voyage-4-lite, cohere embed-english-v3, ollama bge-large-en-v1.5
    EMBEDDING_PROVIDER: str = "voyage"
    EMBEDDING_MODEL: str = "voyage-4-lite"  # Override per-provider (e.g. "embed-english-v3", "bge-large-en-v1.5")
    EMBEDDING_DIM: int = 1024  # Must match Qdrant collection vector size
    # Max texts sent to the embedding provider in a single request. The default
    # is chosen to stay within Voyage's real-time endpoint ceiling of ~120K
    # tokens/request: with CHUNK_SIZE=1500 chars (~300-375 tokens per chunk),
    # 256 chunks is ~80-96K tokens. It also fits under the 1,000-example
    # per-request cap. Tune up or down based on your provider's documented
    # limits and observed latency.
    EMBEDDING_BATCH_SIZE: int = 256
    OLLAMA_BASE_URL: str = "http://localhost:11434"  # For EMBEDDING_PROVIDER=ollama

    # Reranker Provider Settings (pluggable)
    # Supported: voyage (default), cohere, none (skip reranking — fully offline)
    RERANK_PROVIDER: str = "voyage"
    RERANK_MODEL: str = "rerank-2.5"  # Override per-provider (e.g. "rerank-english-v3.0")
    
    # Gemini Model Settings - Different models for different use cases
    GEMINI_MODEL_MAIN: str = "gemini-2.5-flash"  # Main model for answer generation (higher accuracy)
    GEMINI_MODEL_LITE: str = "gemini-2.5-flash-lite"  # Lite model for low-latency tasks (routing, validation)
    
    # Qdrant Settings (local Docker Qdrant via docker-compose; no API key needed)
    QDRANT_URL: Optional[str] = None  # Required for vector store, validated on use
    QDRANT_COLLECTION_NAME: str = "cora_dense_only"
    QDRANT_TIMEOUT: int = 120
    # Max points per Qdrant upsert request. Keeps payload size reasonable for
    # documents that produce many chunks (e.g., 1000+ page PDFs). Qdrant is
    # local, but very large single requests can still hit gRPC/HTTP message
    # limits or memory spikes.
    QDRANT_UPSERT_BATCH_SIZE: int = 1000

    # Qdrant Payload Filter Settings
    # Comma-separated list of metadata fields allowed for filtering queries
    # Fields must match actual payload structure in Qdrant
    # Core fields (always available): source, doc_type, registry, document_id
    # CSV columns are auto-discovered during ingestion if QDRANT_AUTO_INDEX_CSV_COLUMNS=true
    # Note: VCM domain is wide with diverse data sources, so comprehensive field list is maintained
    QDRANT_ALLOWED_FILTER_FIELDS: str = (
        "source,file_type,doc_type,category,registry,standard,publisher,policy_framework,"
        "document_id,version_number,title,methodology_codes,"
        "country,status,program_name,date,methodology_name,reference_id,"
        "chunk_index,source_chunk_index,block_index,json_index"
    )

    # Retrieval Settings
    MAX_CHUNKS_PER_SOURCE: int = 5  # Post-rerank source diversity cap; 0 disables

    # Chunking Settings (indexing-time, used by src/document_store/indexer.py)
    # Tuned via chunk-size A/B test: 1500/300 won over 600/800/1000/1200/2000
    # on faithfulness + completeness with zero hedging across 15 queries
    # judged by OpenRouter Gemini.
    CHUNK_SIZE: int = 1500
    CHUNK_OVERLAP: int = 300
    
    # Multi-round retrieval settings (expansion-pool design)
    # Round 1 fetches candidates; if the pool is sparse, round 2 fetches MORE
    # candidates from the same dense index. The merged pool is then reranked
    # in a single pass to ROUND1_K — one coherent ranking, one score scale.
    # Round 2 is NOT a separate refinement pass; it only expands the candidate
    # pool before the single rerank. There is no per-round threshold for round 2.
    DARTBOARD_ROUNDS: int = 2  # 1 = single pass, 2 = expand pool if sparse
    ROUND1_K: int = 15  # Final top-K after reranking (the only result count)
    ROUND1_THRESHOLD: float = 0.3  # Score threshold (only used when reranking is disabled)
    ROUND2_CANDIDATES: int = 30  # How many candidates round 2 fetches to expand the pool
    # Relevance floor applied to RERANK scores. Reranked docs scoring below this
    # are dropped; if NONE clear the floor, retrieval returns empty so the
    # orchestrator falls back to web search instead of answering from off-topic
    # KB chunks. Set to 0 to disable. Voyage/Cohere rerank scores are in [0, 1].
    RERANK_SCORE_THRESHOLD: float = 0.2
    # KB confidence gate: minimum TOP rerank score for the KB to be considered
    # confidently relevant. If the best retrieved doc scores below this, the
    # orchestrator routes the query to web search instead of answering from
    # topically-adjacent-but-wrong KB chunks (the "confidently wrong" failure
    # mode). Higher than RERANK_SCORE_THRESHOLD: a doc can clear the hard floor
    # yet still be too weak to trust as the sole basis for an answer. Set to 0
    # to disable. Only applied when web search is enabled.
    KB_MIN_TOP_RELEVANCE_SCORE: float = 0.4
    # Pre-LLM lexical overlap guard. After reranking, if the MEAN lexical
    # overlap (fraction of query content words found in each doc) across the
    # top-K docs is below this threshold, retrieval returns empty so the
    # orchestrator falls back to web search. This catches the case where the
    # reranker gives a borderline-passing score to a topically-adjacent-but-
    # wrong doc (e.g. query "just transition mechanism" retrieves VCM docs
    # that mention "transition" in a different context). Zero-cost: pure
    # string matching, no LLM/embedding call. Set to 0 to disable.
    QUERY_DOC_OVERLAP_THRESHOLD: float = 0.0

    # Collection-level domain extensibility (VCM remains the default)
    # Optional description of the KB contents for the router prompt. When set, it
    # is appended to the default VCM description so non-VCM documents can also be
    # routed accurately.
    COLLECTION_DESCRIPTION: Optional[str] = None
    # Optional file path to a JSON file with extra RegistryPattern definitions
    # for non-VCM document IDs. These are merged with the built-in VCM patterns.
    CUSTOM_REGISTRY_PATTERNS: Optional[str] = None
    # Optional override for the system instruction expertise block. When set, it
    # replaces the default VCM expertise list so the LLM can answer from other
    # document domains without VCM bias.
    COLLECTION_SYSTEM_INSTRUCTION: Optional[str] = None
    # Temporal cutoff for market/pricing data. None means "current year - 1".
    # Set to a fixed year (e.g. 2025) if the KB has a known static cutoff.
    KB_MARKET_DATA_CUTOFF_YEAR: Optional[int] = None
    # Per-collection overrides for relevance thresholds. JSON string mapping
    # collection name -> {"kb_min_top_relevance_score", "rerank_score_threshold",
    # "citation_min_relevance_score", "similarity_threshold"}. Falls back to the
    # global settings above when a collection or key is missing.
    COLLECTION_RELEVANCE_OVERRIDES: Optional[str] = None

    # Multi-Agent RAG Settings
    # Web search enabled for queries requiring real-time information
    # Query sanitization is applied automatically (see src/agents/web_search.py)
    ENABLE_QUERY_REWRITING: bool = True
    USE_QUICK_REWRITE: bool = True  # True = local acronym expansion only (faster, ~200ms saved)
    ENABLE_ROUTING: bool = True
    ENABLE_WEB_SEARCH: bool = True  # Enabled: Required for queries outside KB
    ENABLE_VALIDATION: bool = False  # Optional: Enable for critical use cases (adds latency)
    # Disable the post-generation web-supplement relevance check while keeping
    # the separate grounding-validation step controlled by ENABLE_VALIDATION.
    ENABLE_WEB_SUPPLEMENT_RELEVANCE_CHECK: bool = True
    WEB_SUPPLEMENT_RELEVANCE_CONFIDENCE_THRESHOLD: float = 0.8  # Require high confidence before relevance-triggered web supplementation
    
    # Sub-query Fusion Retrieval
    ENABLE_SUBQUERY_FUSION: bool = True  # Use sub-queries from rewriter for multi-query retrieval
    SUBQUERY_CANDIDATES: int = 15  # Dense search candidates per sub-query (main query uses INITIAL_CANDIDATES)
    
    # Answer Generation Optimization
    MAX_CONTEXT_CHARS: int = 16000  # Context size for LLM processing (increased for better retrieval)
    MAX_DOCUMENTS_FOR_ANSWER: int = 10  # Documents passed to answer generator (increased for better coverage)

    # Prompt Repetition Settings (RAG accuracy vs cost)
    ENABLE_VALIDATOR_PROMPT_REPETITION: bool = True
    # If context is longer than this many characters, repeat instructions/question only
    PROMPT_REPETITION_CONTEXT_THRESHOLD: Optional[int] = 12000

    # Citation Settings
    CITATION_MIN_RELEVANCE_SCORE: float = 0.3  # Minimum relevance score to include citation

    # Agent In-Memory Cache TTLs (short-lived, catches rapid-fire duplicates on warm instances)
    ROUTE_CACHE_TTL: int = 600  # 10 minutes
    REWRITE_CACHE_TTL: int = 600  # 10 minutes

    # SQLite Persistent Cache (survives application restarts)
    CACHE_ENABLED: bool = True  # Feature flag for SQLite cache
    CACHE_TTL_SECONDS: int = 86400  # 24 hours

    # API Settings
    TIMEOUT: int = 30

    # Uvicorn server settings (used when running via python -m src.api.main)
    UVICORN_HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # RAG Orchestrator Settings
    RAG_TIMEOUT_MS: int = 45000  # End-to-end orchestrator timeout (ms)

    # Async Query Job Settings (Phase 3)
    ASYNC_QUERY_WORKERS: int = 1  # Number of queue workers for /query/async
    ASYNC_QUERY_QUEUE_MAX_SIZE: int = 100  # Max queued jobs before rejecting new jobs
    ASYNC_QUERY_JOB_TTL_SECONDS: int = 3600  # Retain completed/failed jobs for polling (seconds)
    
    # Security Settings (Phase 3)
    API_ACCESS_KEY: Optional[str] = None  # Optional API key for protected endpoints
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080,http://localhost:8000,http://localhost:5000,http://localhost:5001"
    SECRET_KEY: Optional[str] = None  # Required for history HMAC signing, validated on use
    MEMORY_SECRET_KEY: Optional[str] = None  # Preferred key for memory anonymization/delete tokens; falls back to SECRET_KEY when unset
    
    # PII Redaction Settings (GDPR Compliance)
    PII_REDACTION_ENABLED: bool = True  # Enable PII detection/redaction before memory storage
    
    ENABLE_API_KEY_PROTECTION: bool = False  # Enable API key auth for protected endpoints
    ENABLE_TEST_ENDPOINT: bool = False  # Enable dev-only test query endpoint
    MAX_REQUEST_BODY_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB max request body size
    
    # JWT Authentication Settings
    JWT_SECRET_KEY: Optional[str] = None  # Required for auth, validated on use
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # Token validity duration
    
    # Logging Settings (Phase 3)
    LOG_LEVEL: str = "INFO"
    LOG_JSON_FORMAT: bool = False  # Set True for production log aggregators

    # Authentication Controls
    ENABLE_INSECURE_TOKEN_ENDPOINT: bool = False  # Dev-only token issuance

    # Conversational Handler Settings
    CONVERSATIONAL_INTENT_CACHE_SIZE: int = 512  # LRU cache size for intent classification
    CONVERSATIONAL_INTENT_MAX_TOKENS: int = 5  # Max tokens for intent classification
    CONVERSATIONAL_MAX_OUTPUT_TOKENS: int = 150  # Max tokens for conversational responses

    SEARCH_PROVIDER: str = "tavily"
    TAVILY_API_KEY: Optional[str] = None
    
    # SQLite Settings
    DATABASE_URL: str = "sqlite:///data/cora.db"
    
    # Security: Allowed directories for document processing (absolute paths recommended)
    ALLOWED_DOCUMENT_DIRS: str = "./data,./uploads"  # Comma-separated list of allowed base directories
    DOCUMENT_STORE_ROOT: str = "./data/documents"
    DOCUMENT_UPLOAD_MAX_BYTES: int = 50 * 1024 * 1024
    DOCUMENT_ALLOWED_EXTENSIONS: str = ".pdf,.md,.txt,.csv,.json,.jsonl"
    # PDF render DPI: used by `llm_api` mode to render pages to images for the
    # LLM. `standard` mode (PyMuPDF) extracts text directly and ignores this.
    # 200 is a good accuracy/speed trade-off.
    DOCUMENT_PDF_RENDER_DPI: int = 200
    # Preset prompt for llm_api PDF conversion. Users can override via .env or
    # the settings endpoint to tune conversion for domain-specific documents.
    DOCUMENT_LLM_CONVERSION_PROMPT: str = (
        "Convert this page to clean Markdown for a knowledge base. "
        "Preserve headings, tables, lists, references, and important text. "
        "For images & figures describe them, for mathematical expressions use latex markdown. Return only Markdown."
    )
    # Max HTTP retries for llm_api conversion on 429 (rate limit) / 5xx (server error).
    # Applied via tenacity exponential backoff on the direct HTTP call to the
    # OpenAI-compatible endpoint. Backoff: 5s, 10s, 20s, 40s per page.
    DOCUMENT_LLM_CONVERSION_MAX_RETRIES: int = 4
    # Number of PDF pages to convert in parallel via the LLM API.
    # Default 5 works well for paid API tiers (OpenAI, Gemini paid, OpenRouter).
    # If you hit 429 rate limits, lower this value.
    DOCUMENT_LLM_CONVERSION_CONCURRENCY: int = 5
    # llm_api conversion mode auto-detects the provider via get_llm_settings():
    #   - Gemini  → gemini-2.5-flash  (via Google's OpenAI-compatible endpoint)
    #   - OpenAI  → gpt-4.1-mini      (via OpenAI API)
    # Power users can point llm_api at a local vLLM server (e.g. PaddleOCR-VL-1.6)
    # by setting OPENAI_BASE_URL=http://localhost:8001/v1 — a config change, not a code mode.

    # --- Ingestion concurrency ---
    # Cap how many documents are converted/indexed simultaneously. Docling
    # standard parsing is CPU- and memory-heavy, and embeddings are network-bound;
    # running all uploads in parallel thrashes the machine and can hit API rate
    # limits. A small cap (2) keeps queries responsive while saturating hardware.
    DOCUMENT_INGESTION_CONCURRENCY: int = 2

    # --- Docling standard (classical, non-VLM) PDF conversion ---
    # `standard` mode routes PDFs through Docling's classical pipeline: layout
    # model + OCR + table structure. No VLM is loaded — formula enrichment
    # (do_formula_enrichment) and picture description pull image-text-to-text
    # models (CodeFormulaV2 / SmolVLM), so they are OFF by default to honor the
    # "no VLM" constraint. They can be opted in via .env once a VLM is wanted.
    # OCR engine: rapidocr (default, ONNX, lightweight) | tesseract | onnxtr | easyocr
    DOCUMENT_DOCLING_OCR_ENGINE: str = "rapidocr"
    DOCUMENT_DOCLING_DO_OCR: bool = True
    DOCUMENT_DOCLING_DO_TABLES: bool = True
    # TableFormer mode: "fast" (default — 20% faster, ~70MB less RAM, identical
    # output on benchmarked VCM docs) | "accurate" (better merged-cell recovery
    # on complex tables). See results/docling_benchmark_full/COMPARISON.md.
    DOCUMENT_DOCLING_TABLE_MODE: str = "fast"
    # Formula/code/picture enrichment all load VLMs — OFF by default (no VLM).
    DOCUMENT_DOCLING_DO_FORMULAS: bool = False
    DOCUMENT_DOCLING_MAX_FILE_BYTES: int = 50 * 1024 * 1024
    # Per-document time budget for Standard-mode Docling parsing (seconds).
    # Docling stops and returns PARTIAL_SUCCESS when this is exceeded; we then
    # surface it as a clear timeout error instead of indexing an incomplete doc.
    DOCUMENT_DOCLING_TIMEOUT: float = 1800.0
    # Local directory of pre-downloaded Docling model artifacts. When set, Docling
    # loads models from here instead of fetching on first use. In Docker this
    # points at /app/models/docling (prebaked into the image during build).
    # Override to a volume path (e.g. /app/data/.cache/docling/models) if you
    # want to provide custom models or let models download lazily.
    DOCLING_ARTIFACTS_PATH: Optional[str] = None

    @property
    def allowed_document_dirs_resolved(self) -> list:
        """
        Return resolved absolute paths for allowed document directories.
        
        Resolves relative paths to absolute paths based on current working directory,
        ensuring consistent path validation regardless of execution context.
        """
        from pathlib import Path
        dirs = [d.strip() for d in self.ALLOWED_DOCUMENT_DIRS.split(",") if d.strip()]
        return [str(Path(d).resolve()) for d in dirs]
    
    @field_validator(
        "ASYNC_QUERY_WORKERS", "ASYNC_QUERY_QUEUE_MAX_SIZE", "ASYNC_QUERY_JOB_TTL_SECONDS",
        "CONVERSATIONAL_INTENT_CACHE_SIZE", "CONVERSATIONAL_INTENT_MAX_TOKENS",
        "CONVERSATIONAL_MAX_OUTPUT_TOKENS", "SUBQUERY_CANDIDATES",
        "DOCUMENT_INGESTION_CONCURRENCY", "EMBEDDING_BATCH_SIZE",
        "QDRANT_UPSERT_BATCH_SIZE",
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

    @field_validator("DOCUMENT_DOCLING_TIMEOUT")
    @classmethod
    def validate_positive_timeout(cls, v: float, info) -> float:
        """Ensure the Docling timeout is a positive number."""
        if v <= 0:
            raise ValueError(f"{info.field_name} must be a positive number")
        return v

    _validated_filter_fields: Optional[List[str]] = None

    def get_validated_allowed_filter_fields(self) -> List[str]:
        """
        Return sanitized filter fields from QDRANT_ALLOWED_FILTER_FIELDS.

        Splits the comma-separated string, normalizes field names for Qdrant,
        validates allowed characters and length, and caches the result.

        Raises:
            ValueError: If any configured field contains disallowed characters.
        """
        if self._validated_filter_fields is not None:
            return self._validated_filter_fields

        validated: List[str] = []
        for raw_field in self.QDRANT_ALLOWED_FILTER_FIELDS.split(","):
            field = raw_field.strip()
            if not field:
                continue

            normalized = normalize_filter_field_name(field)
            validated.append(normalized)

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