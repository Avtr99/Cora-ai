"""Generic streaming RAG wrapper.

Works with any LLMClient that implements ``generate_text_stream``.
Replaces the Gemini-specific ``GeminiStreamingClient`` for the streaming
orchestrator path.
"""

from typing import Any, Dict, Optional, AsyncGenerator
import asyncio
import hashlib

from loguru import logger

from .base_rag_client import BaseRAGClient
from .prompts import (
    MAX_QUERY_LENGTH,
    get_system_instruction,
    build_query_prompt,
    _today_utc,
)
from ..utils.cache import query_cache


class StreamingRAGWrapper:
    """Streaming wrapper for any ``BaseRAGClient`` subclass.

    Delegates non-streaming helpers (context preparation, caching,
    sanitization) to the base client and only implements the
    streaming-specific API surface.
    """

    def __init__(self, base_client: BaseRAGClient):
        """Initialize the streaming wrapper.

        Args:
            base_client: Initialized LLMClient (GeminiClient or OpenAICompatibleClient).
        """
        self._base = base_client

    async def check_query_cache(self, query: str) -> Optional[Dict[str, Any]]:
        """Delegate cache check to the base client."""
        return await self._base.check_query_cache(query)

    async def generate_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """Stream content from a prompt, yielding text chunks.

        Prepends the VCM system instruction (same as the non-streaming path).
        """
        formatted_instruction = get_system_instruction().replace("{current_date}", _today_utc())
        full_prompt = f"{formatted_instruction}\n\n{prompt}"

        async for chunk in self._base.generate_text_stream(full_prompt):
            if chunk:
                yield chunk

    async def search_and_process_stream(
        self,
        query: str,
        vector_results: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream-process a query with vector results.

        Yields ``{"type": "token", "chunk": "..."}`` events while the answer
        is generated, then a single ``{"type": "final", "result": {...}}`` event
        with the processed result (sources, coverage, metadata).
        """
        if query is None:
            raise ValueError("Query cannot be None")
        if not isinstance(query, str):
            raise TypeError(f"query must be a string, got {type(query).__name__}")

        query = query.strip()
        if not query:
            raise ValueError("Query cannot be empty")
        if len(query) > MAX_QUERY_LENGTH:
            raise ValueError(f"Query exceeds maximum length of {MAX_QUERY_LENGTH} characters")
        if not isinstance(vector_results, dict):
            raise ValueError("vector_results must be a dictionary")

        sanitized_query, injection_detected = self._base._sanitize_query(query)
        if injection_detected:
            query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]
            logger.warning(f"Potential prompt injection detected. Query hash: {query_hash}")
            query = sanitized_query

        from .post_processor import postprocess_answer
        from .citation_verifier import (
            deduplicate_inline_citations,
            verify_citations,
        )

        try:
            context_text, summaries, sources = self._base._prepare_context(vector_results)
            context_fingerprint = self._base._build_context_fingerprint(context_text, summaries, sources)

            # Context-aware cache check (SQLite)
            cached_result = await query_cache.get_result(query, context_fingerprint=context_fingerprint)
            if cached_result is not None:
                cached_answer = str(cached_result.get("answer", "") or "") if isinstance(cached_result, dict) else ""
                if self._base._should_cache_answer(cached_answer):
                    logger.debug("Serving streaming query from cache")
                    yield {"type": "token", "chunk": cached_answer}
                    yield {"type": "final", "result": cached_result}
                    return
                logger.info("Ignoring stale fallback answer from cache; regenerating")
                try:
                    await query_cache.invalidate(query, context_fingerprint=context_fingerprint)
                except Exception as cache_exc:
                    logger.debug(f"Failed to invalidate stale query cache entry: {cache_exc}")

            prompt = build_query_prompt(
                query,
                context_text,
                summaries,
                include_quiz=False,
                include_suggested_prompts=False,
            )

            accumulated_answer = ""
            chars_out = 0
            async for chunk in self.generate_stream(prompt):
                accumulated_answer += chunk
                chars_out += len(chunk)
                yield {"type": "token", "chunk": chunk}

            answer_text, was_truncated = postprocess_answer(accumulated_answer)

            # Verify and deduplicate citations in the final streamed answer.
            if sources:
                answer_text, _ = verify_citations(answer_text, sources)
                answer_text = deduplicate_inline_citations(answer_text)

            result = {
                "answer": answer_text,
                "sources": sources if sources else ["knowledge_base"],
                "coverage_score": self._base._calculate_coverage_score(
                    context_length=len(context_text),
                    answer_length=len(answer_text),
                    summaries_count=len(summaries),
                ),
                "truncated": was_truncated,
                "meta": {
                    "model": self._base.model_main,
                    "tokens_in": None,
                    "tokens_out": chars_out,
                },
            }

            if self._base._should_cache_answer(answer_text):
                await query_cache.set_result(
                    query,
                    result,
                    context_fingerprint=context_fingerprint,
                )
            else:
                logger.debug("Skipping cache write for explicit fallback answer")

            yield {"type": "final", "result": result}

        except asyncio.CancelledError:
            logger.info("Streaming generation cancelled by upstream timeout/disconnect")
            raise
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Streaming RAG failed. Error: {error_msg[:100]}")
            raise
