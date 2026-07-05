"""Ollama model-listing helpers for the LLM settings routes."""

from typing import Optional, List
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException
from pydantic import BaseModel


class LLMModel(BaseModel):
    """A single available model from a provider."""
    name: str
    size_bytes: Optional[int] = None
    parameter_size: Optional[str] = None
    family: Optional[str] = None


class LLMModelsResponse(BaseModel):
    """Response model for GET /v1/settings/llm/models."""
    models: List[LLMModel] = []


# Hostnames permitted for the Ollama model-listing proxy. Restricting to
# loopback addresses prevents SSRF — the server fetches the URL on the
# user's behalf, so an attacker could otherwise target internal services.
_ALLOWED_OLLAMA_HOSTS = {"localhost", "127.0.0.1", "::1"}
_ALLOWED_OLLAMA_PORT = 11434


def _validate_ollama_url(base_url: str) -> str:
    """Validate that base_url points to a local Ollama instance.

    Returns the normalized URL (scheme + host + port) with no trailing slash.
    Raises HTTPException(400) if the URL is malformed or points to a
    non-local / non-Ollama endpoint.
    """
    parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=400,
            detail="base_url must use http or https scheme.",
        )
    if not parsed.hostname:
        raise HTTPException(
            status_code=400,
            detail="base_url must include a hostname.",
        )
    if parsed.hostname not in _ALLOWED_OLLAMA_HOSTS:
        raise HTTPException(
            status_code=400,
            detail=f"Host '{parsed.hostname}' is not allowed. Only local Ollama instances are supported.",
        )
    port = parsed.port or _ALLOWED_OLLAMA_PORT
    if port != _ALLOWED_OLLAMA_PORT:
        raise HTTPException(
            status_code=400,
            detail=f"Port {port} is not allowed. Ollama must run on port {_ALLOWED_OLLAMA_PORT}.",
        )
    # Rebuild a clean URL to avoid any path/query/userinfo tricks.
    return f"{parsed.scheme}://{parsed.hostname}:{port}"


async def _list_ollama_models(base_url: str) -> LLMModelsResponse:
    """Fetch installed models from Ollama's /api/tags endpoint.

    ``base_url`` must already be validated by ``_validate_ollama_url``.
    """
    url = base_url.rstrip("/") + "/api/tags"

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

    models = []
    for m in data.get("models", []) or []:
        details = m.get("details", {}) or {}
        models.append(LLMModel(
            name=m.get("name", ""),
            size_bytes=m.get("size"),
            parameter_size=details.get("parameter_size"),
            family=details.get("family"),
        ))

    return LLMModelsResponse(models=models)
