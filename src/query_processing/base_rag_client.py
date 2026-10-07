"""Base RAG client with provider-agnostic logic.

Shared by GeminiClient and OpenAICompatibleClient. Contains:
- Context preparation from vector results
- Cache management (SQLite persistent cache)
- Prompt injection detection
- Coverage score calculation
- The search_and_process pipeline (delegates LLM call to subclasses)
"""

from typing import Dict, Any, Optional, List, Tuple, AsyncIterator
import asyncio
import hashlib
import json
from loguru import logger

from ..config import get_settings
from ..utils.cache import query_cache
from .prompts import (
    MAX_QUERY_LENGTH,
    get_system_instruction,
    build_query_prompt,
    _today_utc,
)
from .quiz_utils import should_generate_quiz, split_answer_and_quiz
from .suggested_prompts import (
    should_generate_suggested_prompts,
    split_answer_and_suggested_prompts,
)
from .fallback_answers import NO_ANSWER_FOUND, is_cacheable_answer


class BaseRAGClient:
    """Provider-agnostic RAG logic shared by all LLM clients.

    Subclasses must implement:
    - ``circuit`` property — the provider's circuit breaker
    - ``model_main`` property
    - ``model_lite`` property
    - ``generate_text()`` — for agent LLM calls
    - ``_generate_for_rag()`` — for answer generation (prepends system instruction)
    """

    def __init__(self):
        self._sqlite_cache = None  # Lazily set via attach_sqlite_cache()

    def attach_sqlite_cache(self, cache) -> None:
        """Attach the shared SQLite query cache to this client."""
        self._sqlite_cache = cache

    # ------------------------------------------------------------------
    # Properties — must be implemented by subclasses
    # ------------------------------------------------------------------

    @property
    def circuit(self):
        """Circuit breaker guarding this client's provider calls."""
        raise NotImplementedError

    @property
    def model_main(self) -> str:
        raise NotImplementedError

    @property
    def model_lite(self) -> str:
        raise NotImplementedError

    @property
    def model_relevance(self) -> str:
        """Model used for the post-generation relevance check.

        Defaults to ``model_lite``; providers without a dedicated lite model
        (OpenAI, OpenRouter, etc.) should return ``model_main`` here.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Abstract LLM call — subclasses implement this
    # ------------------------------------------------------------------

    async def _generate_for_rag(self, prompt: str) -> Tuple[str, Dict[str, int]]:
        """Generate answer text for the RAG pipeline.

        Subclasses implement this to call their provider's API.
        The system instruction is prepended by the caller (``search_and_process``).

        Args:
            prompt: The full prompt (system instruction + context + query).

        Returns:
            Tuple of (answer_text, usage_dict) where usage_dict has
            ``{"tokens_in": int, "tokens_out": int}``.
        """
        raise NotImplementedError

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
        """Generate text from a prompt (LLMClient interface)."""
        raise NotImplementedError

    async def generate_text_stream(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
        top_p: float = 0.9,
    ) -> AsyncIterator[str]:
        """Stream text chunks from a prompt."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Shared RAG pipeline
    # ------------------------------------------------------------------

    def get_cache_status(self) -> Dict[str, Any]:
        """Report SQLite cache status for health checks."""
        return {
            "cache_enabled": self._sqlite_cache is not None and self._sqlite_cache.enabled,
            "model": self.model_main,
        }

    async def check_query_cache(self, query: str) -> Optional[Dict[str, Any]]:
        """Check SQLite cache for a previously cached answer (query-only, no context fingerprint)."""
        if not query or not query.strip():
            return None

        query = query.strip()

        # Check SQLite cache with query-only key
        try:
            cached_result = await query_cache.get_result(query)
            if cached_result is not None:
                cached_answer = ""
                cached_sources = None
                if isinstance(cached_result, dict):
                    cached_answer = str(cached_result.get("answer", "") or "")
                    cached_sources = cached_result.get("sources")
                if self._should_cache_answer(cached_answer, cached_sources):
                    logger.debug("Serving from query cache (no-fingerprint fallback)")
                    return cached_result
                logger.info("Ignoring stale fallback answer from query cache (no-fingerprint)")
        except Exception as e:
            logger.debug(f"Query-only cache check failed: {e}")

        return None

    async def persist_to_cache(self, query: str, result: Dict[str, Any]) -> None:
        """Persist a query result to the SQLite cache."""
        if self._sqlite_cache is None or not self._sqlite_cache.enabled:
            return

        if not isinstance(result, dict) or "reasoning_steps" not in result:
            logger.warning(
                "Skipping cache write for query '%s': result is missing reasoning_steps",
                query[:50],
            )
            return

        try:
            settings = get_settings()
            await query_cache.set_result(
                query,
                result,
                context_fingerprint=None,
                ttl=getattr(settings, "CACHE_TTL_SECONDS", 86400),
            )
            logger.debug("Persisted query result to SQLite cache: {}", query[:50])
        except Exception as e:
            logger.warning("Failed to persist query result to SQLite cache: {}", e)

    async def search_and_process(
        self,
        query: str,
        vector_results: Dict[str, Any],
        resolved_query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Full RAG pipeline: build prompt, generate answer, extract citations.

        Provider-agnostic. Delegates the actual LLM call to ``_generate_for_rag``.

        Args:
            query: User query string.
            vector_results: Results from vector store.
            resolved_query: Optional context-resolved form of the query from the
                rewriter, so follow-ups whose subject lives in an earlier turn
                ("what is its effect?") can still be interpreted.
        """
        # Input validation
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

        from ..citations.check import build_citation_correction, check_citations
        from ..citations.context import build_kb_context

        try:
            ctx = build_kb_context(vector_results)
            context_text, summaries, sources = ctx.text, ctx.summaries, ctx.sources
            context_fingerprint = self._build_context_fingerprint(
                context_text, summaries, sources, resolved_query=resolved_query
            )

            # Context-aware cache check (SQLite)
            cached_result = await query_cache.get_result(
                query, context_fingerprint=context_fingerprint
            )
            if cached_result is not None:
                cached_answer = ""
                cached_sources = None
                if isinstance(cached_result, dict):
                    cached_answer = str(cached_result.get("answer", "") or "")
                    cached_sources = cached_result.get("sources")
                if self._should_cache_answer(cached_answer, cached_sources):
                    logger.debug("Serving from query cache (context-aware)")
                    return cached_result
                logger.info("Ignoring stale fallback answer from query cache; regenerating")
                try:
                    await query_cache.invalidate(query, context_fingerprint=context_fingerprint)
                except Exception as cache_exc:
                    logger.debug(f"Failed to invalidate stale query cache entry: {cache_exc}")

            structured_mode = vector_results.get("structured_mode")
            record_count = self._structured_record_count(vector_results)

            # Structured dataset answers are self-contained; do not append
            # quiz or suggested prompts, which would dilute the instructions.
            include_quiz = False if structured_mode else should_generate_quiz(query)
            include_suggested_prompts = False if structured_mode else should_generate_suggested_prompts(query)

            prompt = build_query_prompt(
                query,
                context_text,
                summaries,
                include_quiz=include_quiz,
                include_suggested_prompts=include_suggested_prompts,
                structured_mode=structured_mode,
                resolved_query=resolved_query,
                record_count=record_count,
            )

            # Prepend system instruction (same as GeminiClient._generate_async)
            formatted_instruction = get_system_instruction().replace("{current_date}", _today_utc())
            full_prompt = f"{formatted_instruction}\n\n{prompt}"

            answer_text, usage = await self._generate_for_rag(full_prompt)
            answer_text, quiz_payload, suggested_prompts, was_truncated = self._shape_answer(
                answer_text, structured_mode
            )

            # Citation check: marker numbers are the prompt's own
            # <source index="N"> values, so the only possible errors are
            # out-of-range or missing markers. Retry once with a correction
            # prompt; a still-invalid answer becomes the non-answer sentinel.
            valid_kb_indices = {c.index for c in ctx.citations if c.index is not None}
            if valid_kb_indices:
                citation_errors = check_citations(
                    answer_text, {"knowledge_base": valid_kb_indices}
                )
                if citation_errors:
                    logger.info(
                        "Citation errors detected; retrying once: {}", citation_errors
                    )
                    retry_text, retry_usage = await self._generate_for_rag(
                        build_citation_correction(
                            full_prompt, answer_text, citation_errors, web=False
                        )
                    )
                    for key in ("tokens_in", "tokens_out"):
                        usage[key] = int(usage.get(key, 0)) + int(
                            retry_usage.get(key, 0)
                        )
                    answer_text, quiz_payload, suggested_prompts, was_truncated = (
                        self._shape_answer(retry_text, structured_mode)
                    )
                    citation_errors = check_citations(
                        answer_text, {"knowledge_base": valid_kb_indices}
                    )
                    if citation_errors:
                        logger.info(
                            "Citation errors persist after retry: {}", citation_errors
                        )
                        answer_text = NO_ANSWER_FOUND
                        quiz_payload = None
                        suggested_prompts = None

            # A structured scroll already enumerates the full matching dataset;
            # the response is fully covered by the retrieved records — unless
            # the source file was truncated at the ingestion row limit, in
            # which case coverage is computed like an ordinary result.
            coverage_score = (
                1.0
                if structured_mode and not vector_results.get("structured_partial")
                else self._calculate_coverage_score(
                    context_length=len(context_text),
                    answer_length=len(answer_text),
                    summaries_count=len(summaries),
                )
            )

            result = {
                "answer": answer_text,
                "sources": sources if sources else ["knowledge_base"],
                "coverage_score": coverage_score,
                "truncated": was_truncated,
                # Every citable chunk, numbered exactly as the prompt saw it.
                # Consumers pop this via citations_from_result().
                "context_citations": [c.to_dict() for c in ctx.citations],
                "meta": {
                    "model": self.model_main,
                    "tokens_in": usage.get("tokens_in", 0),
                    "tokens_out": usage.get("tokens_out", 0),
                },
            }

            if quiz_payload:
                result["quiz"] = quiz_payload
            if suggested_prompts:
                result["suggested_prompts"] = suggested_prompts

            if self._should_cache_answer(answer_text, result.get("sources")):
                await query_cache.set_result(
                    query, result, context_fingerprint=context_fingerprint
                )
            else:
                logger.debug("Skipping cache write for explicit fallback answer")
            return result

        except asyncio.CancelledError:
            logger.info("RAG generation was cancelled by upstream timeout/disconnect")
            raise
        except Exception as e:
            error_msg = str(e)
            logger.error(f"RAG generation failed. Error: {error_msg[:100]}")
            raise

    # ------------------------------------------------------------------
    # Shared helper methods (provider-agnostic)
    # ------------------------------------------------------------------

    def _shape_answer(
        self, raw_answer: str, structured_mode: Optional[str]
    ) -> Tuple[str, Any, Any, bool]:
        """Split quiz/suggested-prompt blocks, postprocess, dedupe markers.

        Shared by the first generation and the single citation-correction
        retry so both attempts produce an identically shaped result.
        """
        from .post_processor import postprocess_answer
        from ..citations.markers import deduplicate_inline_citations

        answer_text, quiz_payload = split_answer_and_quiz(raw_answer)
        answer_text, suggested_prompts = split_answer_and_suggested_prompts(answer_text)
        answer_text, was_truncated = postprocess_answer(
            answer_text, structured_mode=structured_mode
        )
        answer_text = deduplicate_inline_citations(answer_text)
        return answer_text, quiz_payload, suggested_prompts, was_truncated

    @staticmethod
    def _structured_record_count(vector_results: Dict[str, Any]) -> Optional[int]:
        """Return the record count carried by a structured-mode retrieval result."""
        metadatas = vector_results.get("metadatas", []) or []
        for meta in metadatas:
            if isinstance(meta, dict) and "structured_record_count" in meta:
                return int(meta["structured_record_count"])
        return None

    @staticmethod
    def _build_context_fingerprint(
        context_text: str,
        summaries: List[str],
        sources: List[str],
        resolved_query: Optional[str] = None,
    ) -> str:
        """Build a stable fingerprint for the retrieval context.

        ``resolved_query`` participates in the fingerprint because it is part of
        the prompt: the same question with a different context resolution is a
        different generation and must not share a cache entry.
        """
        payload = {
            "context": context_text,
            "summaries": summaries,
            "sources": sources,
            "resolved_query": resolved_query or "",
        }
        serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _should_cache_answer(answer_text: str, sources: Optional[List[str]] = None) -> bool:
        """Return whether the generated answer should be persisted in query cache."""
        return is_cacheable_answer(answer_text, sources)

    def _calculate_coverage_score(
        self, context_length: int, answer_length: int, summaries_count: int
    ) -> float:
        """Calculate coverage score based on available context."""
        if context_length == 0:
            return 0.0

        context_factor = min(context_length / 5000, 1.0)
        summary_factor = min(summaries_count / 5, 1.0) if summaries_count > 0 else 0
        answer_factor = min(answer_length / 200, 1.0) if answer_length > 0 else 0

        score = 0.5 * context_factor + 0.3 * summary_factor + 0.2 * answer_factor
        return round(min(score, 1.0), 2)
