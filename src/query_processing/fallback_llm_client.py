"""LLMClient wrapper that falls back to a secondary provider on quota errors.

The primary provider is the one configured in settings (DB or .env). The
fallback is the opposite provider if its API key is also available in the
environment. When the primary hits a 429 / RESOURCE_EXHAUSTED / rate-limit,
the wrapper transparently retries the same call against the fallback provider.
"""

import re
from typing import Any, AsyncIterator, Dict, Optional
from loguru import logger

from .base_rag_client import BaseRAGClient
from .llm_provider import LLMClient


# Patterns that indicate the provider rejected the request due to quota or rate
# limits. These are matched against the exception string.
_QUOTA_PATTERNS = [
    re.compile(r"\b429\b"),
    re.compile(r"resource_exhausted"),
    re.compile(r"rate[_\s]limit"),
    re.compile(r"quota"),
    re.compile(r"circuit is open"),
]


def _is_quota_error(exception: Exception) -> bool:
    """Return True if the exception signals a quota/rate-limit error."""
    msg = str(exception).lower()
    return any(pattern.search(msg) for pattern in _QUOTA_PATTERNS)


class FallbackLLMClient(BaseRAGClient):
    """Transparently retry LLM calls against a fallback provider on quota errors.

    Inherits from :class:`BaseRAGClient` so the streaming RAG wrapper can use its
    provider-agnostic helpers (context preparation, caching, citation scoring).
    Implements the :class:`LLMClient` protocol so it can be used anywhere a
    concrete provider is expected (orchestrator, web search, summarization, etc.).
    """

    def __init__(self, primary: LLMClient, fallback: LLMClient):
        super().__init__()
        self.primary = primary
        self.fallback = fallback
        # Re-use the primary's L2 cache handle so the orchestrator's persistence
        # path works without re-initializing a second cache.
        if hasattr(primary, "_l2_cache"):
            self._l2_cache = primary._l2_cache

    @property
    def model_main(self) -> str:
        """Primary model name (valid for generate_text)."""
        return self.primary.model_main

    @property
    def model_lite(self) -> str:
        """Primary lite model name (valid for generate_text)."""
        return self.primary.model_lite

    @property
    def model_relevance(self) -> str:
        """Primary relevance-check model name (valid for generate_text)."""
        return self.primary.model_relevance

    def _warn_fallback(self, streaming: bool = False) -> None:
        """Log a consistent warning when falling back to the secondary provider."""
        action = "streaming " if streaming else ""
        logger.warning(
            f"Primary LLM ({self.primary.model_main}) hit quota/rate-limit; "
            f"falling back to {action}{self.fallback.model_main}"
        )

    async def generate_text(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
        top_p: float = 0.9,
        max_output_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> str:
        """Generate text using the primary provider, falling back on quota errors."""
        try:
            return await self.primary.generate_text(
                prompt,
                model=model,
                temperature=temperature,
                top_p=top_p,
                max_output_tokens=max_output_tokens,
                json_mode=json_mode,
            )
        except Exception as e:
            if _is_quota_error(e):
                self._warn_fallback()
                return await self.fallback.generate_text(
                    prompt,
                    model=self.fallback.model_main,
                    temperature=temperature,
                    top_p=top_p,
                    max_output_tokens=max_output_tokens,
                    json_mode=json_mode,
                )
            raise

    async def generate_text_stream(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
        top_p: float = 0.9,
    ) -> AsyncIterator[str]:
        """Stream text using the primary provider, falling back on the first quota error."""
        primary_iter = self.primary.generate_text_stream(
            prompt,
            model=model,
            temperature=temperature,
            top_p=top_p,
        )
        try:
            first_chunk = await primary_iter.__anext__()
        except Exception as e:
            if _is_quota_error(e):
                self._warn_fallback(streaming=True)
                async for chunk in self.fallback.generate_text_stream(
                    prompt,
                    model=self.fallback.model_main,
                    temperature=temperature,
                    top_p=top_p,
                ):
                    yield chunk
                return
            raise

        yield first_chunk
        async for chunk in primary_iter:
            yield chunk

    async def search_and_process(self, query: str, vector_results: Any) -> Dict[str, Any]:
        """Run the full RAG pipeline on the primary, falling back on quota errors."""
        try:
            return await self.primary.search_and_process(query, vector_results)
        except Exception as e:
            if _is_quota_error(e):
                self._warn_fallback()
                return await self.fallback.search_and_process(query, vector_results)
            raise

    def get_status(self) -> Dict[str, Any]:
        """Return status for both providers, including readable model names."""
        return {
            "primary": self.primary.get_status(),
            "fallback": self.fallback.get_status(),
            "model_main": f"{self.primary.model_main} (fallback: {self.fallback.model_main})",
            "model_lite": f"{self.primary.model_lite} (fallback: {self.fallback.model_lite})",
            "model_relevance": f"{self.primary.model_relevance} (fallback: {self.fallback.model_relevance})",
        }

    async def check_query_cache(self, query: str) -> Optional[Dict[str, Any]]:
        """Delegate cache lookup to the primary provider."""
        if hasattr(self.primary, "check_query_cache"):
            return await self.primary.check_query_cache(query)
        return None

    async def persist_to_l2(self, query: str, result: Dict[str, Any]) -> None:
        """Delegate L2 cache persistence to the primary provider."""
        if hasattr(self.primary, "persist_to_l2"):
            await self.primary.persist_to_l2(query, result)

    def get_cache_status(self) -> Dict[str, Any]:
        """Delegate cache status to the primary provider if available."""
        if hasattr(self.primary, "get_cache_status"):
            return self.primary.get_cache_status()
        return {"cache_enabled": False}

