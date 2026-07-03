"""Settings API routes.

Provides endpoints for:
- GET  /v1/settings/llm        — Get current LLM provider config (never returns API key)
- PUT  /v1/settings/llm        — Update LLM provider config
- GET  /v1/settings/llm/models — List available models for a provider (e.g. Ollama /api/tags)
- POST /v1/settings/llm/test   — Test an LLM config before saving (validates key + model)
- GET  /v1/settings/status     — Full configuration status with validation warnings
"""

from fastapi import APIRouter

from .llm import router as llm_router
from .embeddings import router as embeddings_router
from .search import router as search_router
from .reranker import router as reranker_router
from .status import router as status_router

router = APIRouter(prefix="/settings", tags=["settings"])
router.include_router(llm_router)
router.include_router(embeddings_router)
router.include_router(search_router)
router.include_router(reranker_router)
router.include_router(status_router)
