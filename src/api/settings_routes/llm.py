"""LLM provider settings routes (router aggregator).

The actual handlers live in focused submodules:
- llm_config.py     -- GET/PUT /v1/settings/llm
- llm_profiles.py   -- POST /v1/settings/llm/switch, GET /v1/settings/llm/providers
- llm_ollama.py     -- GET /v1/settings/llm/models
- llm_test.py       -- POST /v1/settings/llm/test
"""

from fastapi import APIRouter

from .llm_config import router as config_router
from .llm_profiles import router as profiles_router
from .llm_ollama import router as ollama_router
from .llm_test import router as test_router

router = APIRouter()
router.include_router(config_router)
router.include_router(profiles_router)
router.include_router(ollama_router)
router.include_router(test_router)
