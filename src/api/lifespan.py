"""
Application Lifespan Manager

Handles FastAPI application startup and shutdown lifecycle including:
- Component initialization (retriever, LLM client, orchestrator)
- Graceful shutdown with cleanup
"""
import asyncio
from contextlib import asynccontextmanager
from threading import Lock
from loguru import logger

from ..config import get_settings, get_collection_threshold
from .async_query_jobs import get_async_query_job_manager
from ..db.database import run_migrations
from ..query_processing.llm_factory import create_llm_client, is_llm_configured

# Global component instances
retriever = None
llm_client = None  # LLMClient (GeminiClient or OpenAICompatibleClient)
rag_orchestrator = None
citation_manager = None

# Docling DocumentConverter singleton (lazy — built on first standard PDF conversion,
# not at startup, so a missing Docling install never breaks app startup). None until
# first successful build; stays None if Docling is not installed.
_docling_converter = None
_docling_lock = Lock()

_llm_swap_lock = asyncio.Lock()

# Initialization state tracking
initialization_complete = False
initialization_errors = []

# Graceful shutdown state
shutdown_event = asyncio.Event()


async def initialize_components():
    """Initialize heavy components in background."""
    global retriever, llm_client, rag_orchestrator, citation_manager, initialization_complete

    # Clear previous initialization errors for fresh state
    initialization_errors.clear()

    # Import here to avoid triggering module-level get_settings() during app startup
    from ..retrieval.langchain_retriever import LangChainRetriever
    from ..agents import OrchestratorConfig
    from ..agents.streaming_orchestrator import StreamingRAGOrchestrator
    from ..citations import CitationManager
    
    settings = get_settings()
    
    # Check security configuration
    # SECRET_KEY may have been auto-generated and persisted by _apply_db_overlay
    # during get_settings(). If it's still missing, the DB wasn't available.
    if not settings.SECRET_KEY:
        logger.warning(
            "--- SECURITY WARNING --- "
            "SECRET_KEY is not configured and could not be auto-generated. "
            "Conversation history will be DISCARDED for all requests because it cannot be securely verified. "
            "Set SECRET_KEY in .env or ensure the SQLite database is writable."
        )
    
    try:
        logger.info("Initializing retriever...")
        retriever = LangChainRetriever(retrieval_rounds=settings.DARTBOARD_ROUNDS)
        logger.info("Retriever initialized successfully")
    except Exception as e:
        error_msg = f"Failed to initialize retriever: {type(e).__name__}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        initialization_errors.append({"component": "retriever", "error": error_msg})
    
    try:
        if not is_llm_configured():
            logger.warning(
                "No LLM provider configured. The app will start in setup mode. "
                "Configure via /v1/settings/llm endpoint or .env file."
            )
        else:
            logger.info("Initializing LLM client...")
            llm_client = create_llm_client()
            logger.info(f"LLM client initialized: {type(llm_client).__name__}")
    except Exception as e:
        error_msg = f"Failed to initialize LLM client: {type(e).__name__}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        initialization_errors.append({"component": "llm_client", "error": error_msg})

    if retriever and llm_client:
        try:
            logger.info("Initializing RAG Orchestrator...")

            orchestrator_config = OrchestratorConfig(
                enable_rewriting=settings.ENABLE_QUERY_REWRITING,
                use_quick_rewrite=settings.USE_QUICK_REWRITE,
                enable_routing=settings.ENABLE_ROUTING,
                retrieval_k=settings.ROUND1_K,
                retrieval_threshold=settings.ROUND1_THRESHOLD,
                retrieval_rounds=settings.DARTBOARD_ROUNDS,
                kb_min_top_relevance_score=get_collection_threshold(
                    settings, "KB_MIN_TOP_RELEVANCE_SCORE"
                ),
                enable_web_search=settings.ENABLE_WEB_SEARCH,
                enable_web_supplement_relevance_check=settings.ENABLE_WEB_SUPPLEMENT_RELEVANCE_CHECK,
                web_supplement_relevance_confidence_threshold=getattr(
                    settings,
                    "WEB_SUPPLEMENT_RELEVANCE_CONFIDENCE_THRESHOLD",
                    0.8,
                ),
                enable_validation=settings.ENABLE_VALIDATION,
                max_total_time_ms=settings.RAG_TIMEOUT_MS,
            )

            rag_orchestrator = await StreamingRAGOrchestrator.create(
                llm_client=llm_client,
                retriever=retriever,
                answer_generator=llm_client,
                config=orchestrator_config,
            )
            logger.info("RAG Orchestrator initialized successfully")
        except Exception as e:
            error_msg = f"Failed to initialize RAG Orchestrator: {type(e).__name__}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            initialization_errors.append({"component": "rag_orchestrator", "error": error_msg})
    
    
    try:
        logger.info("Initializing Citation Manager...")
        citation_manager = CitationManager(
            min_relevance_score=get_collection_threshold(
                settings, "CITATION_MIN_RELEVANCE_SCORE"
            )
        )
        logger.info("Citation Manager initialized successfully")
    except Exception as e:
        error_msg = f"Failed to initialize Citation Manager: {type(e).__name__}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        initialization_errors.append({"component": "citation_manager", "error": error_msg})
    
    # Check critical components
    if retriever is None or llm_client is None:
        if not is_llm_configured():
            logger.warning("LLM not configured — running in setup mode. Visit /setup to configure.")
        else:
            logger.critical("Critical components failed to initialize. Service cannot operate.")
            logger.critical(f"Initialization errors: {initialization_errors}")
        initialization_complete = False
    else:
        try:
            # Start async query queue workers (Phase 3)
            async_job_manager = get_async_query_job_manager()
            await async_job_manager.configure(
                max_queue_size=settings.ASYNC_QUERY_QUEUE_MAX_SIZE,
                job_ttl_seconds=settings.ASYNC_QUERY_JOB_TTL_SECONDS,
            )
            await async_job_manager.start(worker_count=settings.ASYNC_QUERY_WORKERS)

            # Wire SQLite cache into LLM client for query-only cache lookups.
            # For FallbackLLMClient, propagate to primary + fallback so delegated
            # cache operations (persist_to_cache, check_query_cache) work correctly.
            try:
                from ..db.sqlite_cache import get_sqlite_cache
                sqlite_cache = await get_sqlite_cache()
                if llm_client is not None and sqlite_cache is not None:
                    llm_client._sqlite_cache = sqlite_cache
                    for inner in getattr(llm_client, "primary", None), getattr(llm_client, "fallback", None):
                        if inner is not None:
                            inner._sqlite_cache = sqlite_cache
            except Exception as e:
                logger.warning(f"Failed to wire SQLite cache into LLM client (non-critical): {e}")

            # Pre-populate the dynamic filter-field cache. This makes
            # synchronous Qdrant scroll calls; doing it here (in a thread)
            # keeps the first user query from blocking the event loop.
            try:
                settings = get_settings()
                collection_name = getattr(settings, "QDRANT_COLLECTION_NAME", None)
                if collection_name:
                    from ..retrieval.schema_discovery import discover_fields_from_payloads
                    await asyncio.to_thread(discover_fields_from_payloads, collection_name)
                    logger.info("Filter-field schema discovery completed")
            except Exception as e:
                logger.warning(f"Filter-field discovery failed (non-critical): {e}")

            initialization_complete = True
            logger.info("All components initialized successfully")
        except Exception as e:
            error_msg = f"Failed to initialize async query manager: {type(e).__name__}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            initialization_errors.append({"component": "async_query_jobs", "error": error_msg})
            initialization_complete = False




@asynccontextmanager
async def lifespan(app):
    """Application lifespan manager for startup and shutdown."""
    
    logger.info("Starting VCM Assistant API...")
    
    # Run SQLite migrations synchronously before starting components
    try:
        run_migrations()
        logger.info("SQLite migrations completed successfully")
    except Exception as e:
        logger.error(f"Failed to run SQLite migrations: {e}")

    # Ensure document store tables exist once at startup (avoids per-request checks)
    try:
        from ..document_store.storage import ensure_document_store_tables, recover_interrupted_documents
        ensure_document_store_tables()
        logger.info("Document store tables ensured")
        # Recover any documents left in an in-flight status by a previous
        # crash/restart. Without this they stay "converting" forever.
        try:
            recovered = recover_interrupted_documents()
            if recovered:
                logger.warning(
                    f"Recovered {recovered} document(s) stuck in an in-flight status "
                    "after server restart — marked as failed."
                )
        except Exception as e:
            logger.error(f"Document store recovery sweep failed: {e}")
    except Exception as e:
        logger.error(f"Failed to ensure document store tables: {e}")
    
    # Start initialization in background task
    init_task = asyncio.create_task(initialize_components())
    
    try:
        # Yield immediately to allow FastAPI to start listening on port
        yield
    finally:
        # Shutdown: Clean up resources
        logger.info("Shutting down VCM Assistant API...")
        shutdown_event.set()

        # Stop async query queue workers
        try:
            async_job_manager = get_async_query_job_manager()
            await async_job_manager.stop()
        except Exception as e:
            logger.error(
                f"Failed to stop async query manager during shutdown: {type(e).__name__}: {str(e)}",
                exc_info=True,
            )
        
        # Cancel init task if still running
        if not init_task.done():
            init_task.cancel()
            try:
                await init_task
            except asyncio.CancelledError:
                pass
        
        # Allow in-flight requests to complete (grace period)
        await asyncio.sleep(2)
        logger.info("Shutdown complete")


def get_retriever():
    """Get the retriever instance. Returns None if not initialized."""
    return retriever


def get_gemini_client():
    """Get the LLM client instance. Returns None if not initialized.

    Kept as get_gemini_client() for backwards compatibility with existing callers.
    Returns the LLMClient (GeminiClient or OpenAICompatibleClient).
    """
    return llm_client


def get_llm_client():
    """Get the LLM client instance. Returns None if not initialized."""
    return llm_client


async def hot_swap_llm_client() -> dict:
    """Rebuild the LLM client and RAG orchestrator from current settings.

    Called after the user switches providers via the settings API. Reuses the
    existing retriever and citation_manager - only the LLM client and
    orchestrator are rebuilt. This avoids a full server restart.

    The swap is atomic under a lock: if orchestrator rebuild fails, neither
    global is updated, so callers never see a mismatched client/orchestrator.

    Returns:
        Dict with success status and client type name, or error details.
    """
    global llm_client, rag_orchestrator

    if not is_llm_configured():
        return {"success": False, "error": "No LLM provider configured"}

    async with _llm_swap_lock:
        try:
            new_client = create_llm_client()
            logger.info(
                f"Hot-swap: new LLM client created: {type(new_client).__name__} "
                f"(model: {getattr(new_client, 'model_main', 'unknown')})"
            )
        except Exception as e:
            error_msg = f"Hot-swap failed during client creation: {type(e).__name__}: {e}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg}

        # Wire SQLite cache into the new client (same as startup path).
        # For FallbackLLMClient, propagate to primary + fallback so delegated
        # cache operations (persist_to_cache, check_query_cache) work correctly.
        try:
            from ..db.sqlite_cache import get_sqlite_cache
            sqlite_cache = await get_sqlite_cache()
            if new_client is not None and sqlite_cache is not None:
                new_client._sqlite_cache = sqlite_cache
                # Propagate to inner clients if this is a wrapper
                for inner in getattr(new_client, "primary", None), getattr(new_client, "fallback", None):
                    if inner is not None:
                        inner._sqlite_cache = sqlite_cache
        except Exception as e:
            logger.warning(f"Hot-swap: SQLite cache wiring failed (non-critical): {e}")

        # Rebuild the orchestrator with the new client, reusing the existing
        # retriever and citation_manager.
        if retriever is not None:
            try:
                settings = get_settings()
                from ..agents import OrchestratorConfig
                from ..agents.streaming_orchestrator import StreamingRAGOrchestrator

                orchestrator_config = OrchestratorConfig(
                    enable_rewriting=settings.ENABLE_QUERY_REWRITING,
                    use_quick_rewrite=settings.USE_QUICK_REWRITE,
                    enable_routing=settings.ENABLE_ROUTING,
                    retrieval_k=settings.ROUND1_K,
                    retrieval_threshold=settings.ROUND1_THRESHOLD,
                    retrieval_rounds=settings.DARTBOARD_ROUNDS,
                    kb_min_top_relevance_score=get_collection_threshold(
                        settings, "KB_MIN_TOP_RELEVANCE_SCORE"
                    ),
                    enable_web_search=settings.ENABLE_WEB_SEARCH,
                    enable_web_supplement_relevance_check=settings.ENABLE_WEB_SUPPLEMENT_RELEVANCE_CHECK,
                    web_supplement_relevance_confidence_threshold=getattr(
                        settings,
                        "WEB_SUPPLEMENT_RELEVANCE_CONFIDENCE_THRESHOLD",
                        0.8,
                    ),
                    enable_validation=settings.ENABLE_VALIDATION,
                    max_total_time_ms=settings.RAG_TIMEOUT_MS,
                )

                rag_orchestrator = await StreamingRAGOrchestrator.create(
                    llm_client=new_client,
                    retriever=retriever,
                    answer_generator=new_client,
                    config=orchestrator_config,
                )
                logger.info("Hot-swap: RAG orchestrator rebuilt successfully")
            except Exception as e:
                error_msg = f"Hot-swap: orchestrator rebuild failed: {type(e).__name__}: {e}"
                logger.error(error_msg, exc_info=True)
                # Still swap the client - direct callers via get_llm_client() get
                # the new client. The old orchestrator keeps the old client, which
                # is better than no orchestrator for streaming queries.
        else:
            logger.warning("Hot-swap: retriever not available, skipping orchestrator rebuild")

        # Atomic update: both globals are assigned only after client and
        # orchestrator are successfully rebuilt.
        llm_client = new_client
    return {
        "success": True,
        "client_type": type(new_client).__name__,
        "model": getattr(new_client, "model_main", "unknown"),
    }



def get_rag_orchestrator():
    """Get the RAG orchestrator instance. Returns None if not initialized."""
    return rag_orchestrator


def get_citation_manager():
    """Get the citation manager instance. Returns None if not initialized."""
    return citation_manager


def get_initialization_status():
    """Get initialization status for health checks."""
    return {
        "complete": initialization_complete,
        "errors": initialization_errors,
        "components": {
            "retriever": retriever is not None,
            "llm_client": llm_client is not None,
            "rag_orchestrator": rag_orchestrator is not None,
            "citation_manager": citation_manager is not None,
        }
    }


def _build_docling_converter():
    """Construct a Docling DocumentConverter from settings (classical, non-VLM).

    Lazy-imports Docling so app startup never fails when Docling is not installed
    (INSTALL_INGESTION=false). Only the classical pipeline is configured: layout
    model + OCR + table structure. Formula/code/picture enrichment are left off
    (they load VLMs: CodeFormulaV2 / SmolVLM) — do_formula_enrichment is the single
    opt-in knob via DOCUMENT_DOCLING_DO_FORMULAS. Models load once and are reused.
    """
    from pathlib import Path

    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
    from docling.document_converter import DocumentConverter, PdfFormatOption

    settings = get_settings()

    pipeline_options = PdfPipelineOptions(
        do_ocr=settings.DOCUMENT_DOCLING_DO_OCR,
        do_table_structure=settings.DOCUMENT_DOCLING_DO_TABLES,
        do_formula_enrichment=settings.DOCUMENT_DOCLING_DO_FORMULAS,
        enable_remote_services=False,
        document_timeout=settings.DOCUMENT_DOCLING_TIMEOUT,
    )

    # OCR engine is swappable via setting. RapidOCR is our default (lightweight,
    # ONNX-based, no C deps). Docling's built-in default is EasyOCR, so every
    # engine must be set explicitly — including RapidOCR.
    engine = settings.DOCUMENT_DOCLING_OCR_ENGINE.lower()
    if engine == "rapidocr":
        from docling.datamodel.pipeline_options import RapidOcrOptions

        # VCM documents are English. Docling's default is Chinese, which would
        # download Chinese PP-OCRv4 models and produce worse OCR on English text.
        pipeline_options.ocr_options = RapidOcrOptions(lang=["english"])
    elif engine == "tesseract":
        from docling.datamodel.pipeline_options import TesseractOcrOptions

        pipeline_options.ocr_options = TesseractOcrOptions()
    elif engine == "easyocr":
        from docling.datamodel.pipeline_options import EasyOcrOptions

        pipeline_options.ocr_options = EasyOcrOptions(lang=["en"])
    elif engine == "onnxtr":
        from docling_ocr_onnxtr import OnnxtrOcrOptions

        pipeline_options.ocr_options = OnnxtrOcrOptions()
        pipeline_options.allow_external_plugins = True
    else:
        logger.warning(
            "Unknown DOCUMENT_DOCLING_OCR_ENGINE '%s'; falling back to RapidOCR.", engine
        )
        from docling.datamodel.pipeline_options import RapidOcrOptions

        pipeline_options.ocr_options = RapidOcrOptions()

    # TableFormer accuracy vs speed.
    if settings.DOCUMENT_DOCLING_TABLE_MODE.lower() == "fast":
        pipeline_options.table_structure_options.mode = TableFormerMode.FAST
    else:
        pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE

    # Pre-baked model artifacts (offline / Docker volume). When set, Docling loads
    # models from here instead of fetching on first use.
    if settings.DOCLING_ARTIFACTS_PATH:
        pipeline_options.artifacts_path = Path(settings.DOCLING_ARTIFACTS_PATH)

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        }
    )


def get_docling_converter():
    """Get the Docling DocumentConverter singleton (lazy init, double-checked lock).

    Returns None if Docling is not installed or failed to initialize. The converter
    is built on first use — not at startup — so missing Docling never breaks app
    startup, and model weights download lazily on the first conversion.
    """
    global _docling_converter
    if _docling_converter is not None:
        return _docling_converter
    with _docling_lock:
        if _docling_converter is not None:
            return _docling_converter
        try:
            _docling_converter = _build_docling_converter()
            logger.info("Docling converter initialized (classical, non-VLM pipeline)")
        except ImportError:
            logger.warning("Docling is not installed; standard PDF mode unavailable.")
            return None
        except Exception as e:
            logger.exception("Failed to initialize Docling converter: {}", e)
            return None
    return _docling_converter
