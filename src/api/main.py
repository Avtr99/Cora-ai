"""
VCM Assistant API

Main FastAPI application entry point. Routes and handlers are organized into:
- lifespan.py: Application lifecycle management
- query_routes.py: Query processing endpoints
- document_routes.py: Document management endpoints
- health.py: Health check endpoints
- memory_routes.py: Memory management endpoints
- auth_routes.py: Authentication endpoints
- summarize_routes.py: Document summarization endpoints
"""
from fastapi import FastAPI, HTTPException, Request, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError
from typing import List, Dict, Any, Optional, Literal
import uuid
from datetime import datetime, timezone
from loguru import logger
import asyncio
import json
import os
from urllib.parse import unquote

from .middleware import (
    RequestSizeLimitMiddleware,
    SecurityMiddleware,
    LoggingMiddleware,
    configure_logging,
    get_metrics,
    get_all_circuit_stats,
    register_exception_handlers,
)
from .health import run_health_checks, liveness_check, readiness_check
from .memory_routes import router as memory_router
from .auth_routes import router as auth_router
from .summarize_routes import router as summarize_router
from .document_store_routes import router as document_store_router
from .settings_routes import router as settings_router
from .lifespan import lifespan
from .async_query_jobs import get_async_query_job_manager
from .public_routes import router as public_router
from ..config import get_settings
from .query_routes import Query as QueryModel, Response as QueryResponse, process_query_core
from .streaming_service import process_query_core_stream

# Initialize settings before logging configuration
settings = get_settings()

# Configure structured logging with runtime settings
configure_logging(log_level=settings.LOG_LEVEL, json_logs=settings.LOG_JSON_FORMAT)

# Component instances are managed in lifespan.py
# Use get_retriever(), get_gemini_client(), etc. to access them

app = FastAPI(
    title="VCM Assistant API",
    description="RAG-powered Voluntary Carbon Market Assistant API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    default_response_class=ORJSONResponse,
)

# Register custom exception handlers
register_exception_handlers(app)

# Configure CORS for production
# Read allowed origins from environment variable or use defaults
cors_origins_str = settings.CORS_ORIGINS
ALLOWED_ORIGINS = [origin.strip() for origin in cors_origins_str.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-API-Key",
        "X-Request-ID",
        "X-User-ID",
    ],
    expose_headers=["X-Request-ID", "X-Response-Time"],
)

# Add security middleware (security headers + optional API key auth)
protected_paths = ["/v1", "/api"] if settings.ENABLE_API_KEY_PROTECTION else None
app.add_middleware(
    SecurityMiddleware,
    protected_paths=protected_paths,
    exclude_paths=["/health", "/live", "/ready", "/docs", "/redoc", "/openapi.json"]
)

# Add logging middleware
app.add_middleware(
    LoggingMiddleware,
    exclude_paths=["/health", "/live", "/ready", "/docs", "/redoc", "/openapi.json"]
)

# Add request body size limiting middleware
app.add_middleware(
    RequestSizeLimitMiddleware,
    max_content_length=settings.MAX_REQUEST_BODY_SIZE_BYTES,
    exclude_paths=[
        "/health",
        "/live",
        "/ready",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/v1/documents",
        "/api/documents",
    ]
)

class Document(BaseModel):
    text: str
    metadata: Optional[Dict[str, Any]] = None

class DocumentBatch(BaseModel):
    documents: List[Document]

Query = QueryModel
Response = QueryResponse

class AsyncQueryAcceptedResponse(BaseModel):
    job_id: str
    status: Literal["queued"]
    submitted_at: str
    queue_depth: int

class AsyncQueryStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "processing", "completed", "failed"]
    submitted_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# =============================================================================
# Document ingestion is served by the document_store router at /v1/documents
# (see src/api/document_store_routes.py). Uploads are processed as background
# jobs via src/document_store/{converter,indexer,jobs,storage}.py.
# =============================================================================

@app.post("/query", response_model=Response)
async def process_query(query: Query, request: Request):
    """
    Process a user query using RAG pipeline with security sanitization.
    """
    try:
        return await process_query_core(
            query,
            request,
            include_reasoning=True,
            include_metadata=True,
            include_duration_ms=True,
            include_chat_history_in_orchestrator=True,
        )
        
    except HTTPException:
        raise
    
    except Exception as e:
        error_id = str(uuid.uuid4())[:8]
        logger.exception(f"Error processing query [error_id={error_id}]: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error processing query (error_id: {error_id})"
        )

async def _process_async_query_job(payload: Dict[str, Any], job_id: str) -> Dict[str, Any]:
    """Run queued async query jobs through the same pipeline as /query."""
    class _AsyncRequestState:
        def __init__(self, request_id: str, user_id: str) -> None:
            self.request_id = request_id
            self.user_id = user_id

    class _AsyncRequestContext:
        def __init__(self, request_id: str, user_id: str) -> None:
            self.state = _AsyncRequestState(request_id=request_id, user_id=user_id)

    try:
        query = Query(**payload)
    except ValidationError as exc:
        error_summary = "; ".join(
            f"{'.'.join(str(part) for part in err.get('loc', ()))}: {err.get('msg', 'Invalid value')}"
            for err in exc.errors()
        )
        logger.warning(
            f"Invalid async query payload [job_id={job_id}]: {error_summary}"
        )
        raise HTTPException(status_code=422, detail="Invalid async query payload") from exc

    request_context = _AsyncRequestContext(
        request_id=f"async-{job_id}",
        user_id="async-job",
    )
    result = await process_query(query, request_context)  # type: ignore[arg-type]

    if hasattr(result, "model_dump"):
        return result.model_dump()
    return dict(result)

get_async_query_job_manager().register_processor(_process_async_query_job)

@app.post("/query/async", response_model=AsyncQueryAcceptedResponse, status_code=202)
async def enqueue_query_async(query: Query):
    """Phase 3: Queue long-running query execution and return a job ID."""
    manager = get_async_query_job_manager()
    try:
        return await manager.enqueue(query.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=413, detail="Request payload too large or invalid") from exc
    except asyncio.QueueFull:
        raise HTTPException(
            status_code=503,
            detail="Async query queue is full. Please retry shortly."
        )
    except RuntimeError:
        raise HTTPException(
            status_code=503,
            detail="Async query service is initializing. Please retry shortly."
        )

@app.get("/query/async/{job_id}", response_model=AsyncQueryStatusResponse)
async def get_query_async_status(job_id: str):
    """Get queued async query status/result by job ID."""
    manager = get_async_query_job_manager()
    job = await manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Async query job not found")
    return job

@app.post("/query/stream")
async def process_query_stream(query: Query, request: Request, tokens: bool = True):
    """Stream query processing via SSE with token events and a final payload event.

    Query params:
        tokens: When False, suppress token/replace events — only status,
            result, done, and error events are emitted. Used by clients
            that render the complete answer on result rather than
            streaming tokens (e.g. the web UI).
    """

    async def event_generator():
        stream = process_query_core_stream(
            query,
            request,
            include_reasoning=True,
            include_metadata=True,
            include_duration_ms=True,
            include_chat_history_in_orchestrator=True,
            emit_tokens=tokens,
        )
        try:
            async for event in stream:
                if await request.is_disconnected():
                    logger.info("SSE client disconnected; canceling streaming query")
                    return
                yield f"data: {json.dumps(event)}\n\n"
        except asyncio.CancelledError:
            logger.info("SSE streaming cancelled by client disconnect")
        except Exception:
            error_id = str(uuid.uuid4())[:8]
            logger.exception(f"Error processing streaming query [error_id={error_id}]")
            yield f"data: {json.dumps({'event': 'error', 'error_id': error_id, 'message': 'Internal server error processing query'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# API v1 Router - Versioned API endpoints
# =============================================================================

v1_router = APIRouter(prefix="/v1", tags=["v1"])

@v1_router.post("/query", response_model=Response)
async def v1_process_query(query: Query, request: Request):
    """Process a user query using RAG pipeline."""
    return await process_query(query, request)

@v1_router.post("/query/stream")
async def v1_process_query_stream(query: Query, request: Request, tokens: bool = True):
    """Stream query processing updates (SSE) for API v1."""
    return await process_query_stream(query, request, tokens=tokens)

@v1_router.post("/query/async", response_model=AsyncQueryAcceptedResponse, status_code=202)
async def v1_enqueue_query_async(query: Query):
    """Queue long-running query execution for API v1."""
    return await enqueue_query_async(query)

@v1_router.get("/query/async/{job_id}", response_model=AsyncQueryStatusResponse)
async def v1_get_query_async_status(job_id: str):
    """Get queued async query status/result for API v1."""
    return await get_query_async_status(job_id)

@v1_router.get("/health")
async def v1_health():
    """API v1 health check with component details."""
    return await run_health_checks(include_dependencies=True)


# =============================================================================
# Health Check Endpoints (root level for container probes)
# =============================================================================

@app.get("/health")
async def health():
    """Full health check with component details."""
    return await run_health_checks(include_dependencies=True)


@app.get("/live")
async def live():
    """
    Liveness probe endpoint for container orchestrators.
    Returns immediately if the application process is running.
    """
    return await liveness_check()


@app.get("/ready")
async def ready():
    """
    Readiness probe endpoint for container orchestrators.
    Checks if the application is ready to receive traffic.
    """
    return await readiness_check()


@v1_router.get("/metrics")
async def v1_metrics():
    """Get API v1 performance metrics."""
    return {
        "version": "1.0.0",
        "performance": get_metrics(),
        "circuit_breakers": get_all_circuit_stats(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

if settings.ENABLE_TEST_ENDPOINT:
    # Import and register test query endpoint only when enabled
    from .query_routes import test_query, TestQueryRequest, TestQueryResponse

    @v1_router.post("/test-query", response_model=TestQueryResponse)
    async def v1_test_query(test_request: TestQueryRequest, request: Request):
        """
        Direct query testing endpoint for development.
        
        Allows testing queries directly without frontend, with full debug output.
        Use this to test various queries and see detailed results.
        
        Example:
        ```
        curl -X POST "http://localhost:8000/v1/test-query" \\
             -H "Content-Type: application/json" \\
             -d '{"query": "What is VM0048?"}'
        ```
        """
        return await test_query(request, test_request)


# Include v1 router
app.include_router(v1_router)

# Include auth router under /v1 for consistent versioning
v1_router.include_router(auth_router)

# Include public feedback router under /v1
v1_router.include_router(public_router)

# Include memory router under /v1 for consistent versioning
v1_router.include_router(memory_router)

# Include summarize router under /v1
v1_router.include_router(summarize_router)

# Include settings router under /v1
v1_router.include_router(settings_router)

# Include document store router under /v1 and /api for the local SPA.
app.include_router(document_store_router, prefix="/v1")
app.include_router(document_store_router, prefix="/api")

# Include settings router under /api/v1 for the local SPA (frontend calls /api/v1/settings/*)
app.include_router(settings_router, prefix="/api/v1")

# Include public router under /api for the local SPA (frontend calls /api/submit-feedback)
app.include_router(public_router, prefix="/api")

# -----------------------------------------------------------------------------
# /api/* aliases for production-served SPA
#
# In development, Vite proxies these to the backend. In production, the built
# SPA is served by FastAPI itself, so we need explicit route aliases to prevent
# the SPA catch-all from returning index.html (HTML) for API calls.
# -----------------------------------------------------------------------------

@app.get("/api/cora-health")
async def api_cora_health():
    """Health check alias for the SPA (maps to /health)."""
    return await run_health_checks(include_dependencies=True)

@app.post("/api/cora-query")
async def api_cora_query(query: Query, request: Request):
    """Query alias for the SPA (maps to /v1/query)."""
    return await process_query(query, request)

@app.post("/api/cora-query-stream")
async def api_cora_query_stream(query: Query, request: Request, tokens: bool = True):
    """Streaming query alias for the SPA (maps to /v1/query/stream)."""
    return await process_query_stream(query, request, tokens=tokens)

# Mount SPA (Single Page Application)
# 1. API router is already included under /v1

assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "dist", "assets")
public_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "dist")

# Ensure directories exist so FastAPI doesn't crash on startup if not built yet
os.makedirs(assets_dir, exist_ok=True)
os.makedirs(public_dir, exist_ok=True)

# 2. Mount static assets (JS, CSS, images) explicitly at /assets
app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

# Mount public directory items at the root (like favicon.ico, /data, etc.)
# We skip mounting the entire dist directory at / to avoid shadowing the API
# and SPA fallback. Static items should be accessed via direct paths.
# We will use a catch-all route instead for SPA routing.

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """
    Catch-all route to serve the React SPA.
    Any route that doesn't match an API route or a static asset will fall through here,
    allowing React Router to handle client-side routing.
    """
    # Guard against accidental SPA serving for missed API routes
    if full_path.startswith("v1/") or full_path == "v1":
        raise HTTPException(status_code=404, detail="API route not found")
    if full_path.startswith("api/") or full_path == "api":
        raise HTTPException(status_code=404, detail="API route not found")

    # Reject path traversal attempts (e.g. "..", encoded variants) before
    # joining with the public directory. Without this, a request like
    # GET /../../etc/passwd could escape public_dir via os.path.join.
    if ".." in unquote(full_path).split("/"):
        raise HTTPException(status_code=404, detail="Not Found")

    # Serve static files from the public directory if they exist and aren't directories.
    # Resolve the real path and verify it stays within public_dir to prevent traversal.
    file_path = os.path.join(public_dir, full_path)
    real_public_dir = os.path.realpath(public_dir)
    real_file_path = os.path.realpath(file_path)
    if (
        real_file_path.startswith(real_public_dir + os.sep)
        and os.path.exists(real_file_path)
        and os.path.isfile(real_file_path)
    ):
        return FileResponse(real_file_path)

    # Fallback to index.html for React routing
    index_path = os.path.join(public_dir, "index.html")
    if os.path.exists(index_path):
        response = FileResponse(index_path)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    return ORJSONResponse(content={"error": "Not Found"}, status_code=404)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.UVICORN_HOST, port=settings.PORT)