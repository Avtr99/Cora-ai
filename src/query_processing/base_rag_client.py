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
import html
import json
from loguru import logger

from ..config import get_settings
from ..utils.cache import query_cache
from ..citations import CitationManager
from .prompts import (
    MAX_QUERY_LENGTH,
    MAX_CONTEXT_LENGTH,
    get_system_instruction,
    build_query_prompt,
    _today_utc,
)
from .quiz_utils import should_generate_quiz, split_answer_and_quiz
from .suggested_prompts import (
    should_generate_suggested_prompts,
    split_answer_and_suggested_prompts,
)
from .prompt_guard import get_prompt_guard, PromptInjectionError
from .fallback_answers import is_cacheable_answer


class BaseRAGClient:
    """Provider-agnostic RAG logic shared by all LLM clients.

    Subclasses must implement:
    - ``model_main`` property
    - ``model_lite`` property
    - ``generate_text()`` — for agent LLM calls
    - ``_generate_for_rag()`` — for answer generation (prepends system instruction)
    """

    def __init__(self):
        self._sqlite_cache = None  # Lazily set from lifespan initialization

    # ------------------------------------------------------------------
    # Properties — must be implemented by subclasses
    # ------------------------------------------------------------------

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
            from ..utils.cache import get_query_cache_key, QUERY_HANDLER_TYPE
            settings = get_settings()
            hash_key = get_query_cache_key(query)
            await self._sqlite_cache.set(
                hash_key,
                QUERY_HANDLER_TYPE,
                result,
                ttl_seconds=getattr(settings, "CACHE_TTL_SECONDS", 86400),
            )
            logger.debug("Persisted query result to SQLite cache: %s", query[:50])
        except Exception as e:
            logger.warning("Failed to persist query result to SQLite cache: %s", e)

    async def search_and_process(self, query: str, vector_results: Dict[str, Any]) -> Dict[str, Any]:
        """Full RAG pipeline: build prompt, generate answer, extract citations.

        Provider-agnostic. Delegates the actual LLM call to ``_generate_for_rag``.
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

        # Prompt injection detection
        sanitized_query, injection_detected = self._sanitize_query(query)
        if injection_detected:
            query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]
            logger.warning(f"Potential prompt injection detected. Query hash: {query_hash}")
            query = sanitized_query

        from .post_processor import postprocess_answer
        from .citation_verifier import (
            deduplicate_inline_citations,
            normalize_kb_citations,
            verify_citations,
        )

        try:
            context_text, summaries, sources = self._prepare_context(vector_results)
            context_fingerprint = self._build_context_fingerprint(context_text, summaries, sources)

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

            include_quiz = should_generate_quiz(query)
            include_suggested_prompts = should_generate_suggested_prompts(query)

            prompt = build_query_prompt(
                query, context_text, summaries,
                include_quiz=include_quiz,
                include_suggested_prompts=include_suggested_prompts,
            )

            # Prepend system instruction (same as GeminiClient._generate_async)
            formatted_instruction = get_system_instruction().replace("{current_date}", _today_utc())
            full_prompt = f"{formatted_instruction}\n\n{prompt}"

            answer_text, usage = await self._generate_for_rag(full_prompt)
            answer_text, quiz_payload = split_answer_and_quiz(answer_text)
            answer_text, suggested_prompts = split_answer_and_suggested_prompts(answer_text)
            answer_text, was_truncated = postprocess_answer(answer_text)

            # Citation verification: ensure every [source] in the answer
            # matches a retrieved source. Repairs fuzzy matches, removes
            # hallucinated citations.
            if sources:
                answer_text, unmatched = verify_citations(answer_text, sources)
                answer_text = deduplicate_inline_citations(answer_text)
                answer_text = normalize_kb_citations(answer_text, sources)

            result = {
                "answer": answer_text,
                "sources": sources if sources else ["knowledge_base"],
                "coverage_score": self._calculate_coverage_score(
                    context_length=len(context_text),
                    answer_length=len(answer_text),
                    summaries_count=len(summaries),
                ),
                "truncated": was_truncated,
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

    def _prepare_context(self, vector_results: Dict[str, Any]) -> Tuple[str, List[str], List[str]]:
        """Extract context from vector payload.

        Each chunk is wrapped with a human-readable <source> tag so the LLM can
        cite documents by their real titles instead of internal doc IDs.
        """
        docs = vector_results.get("documents", [])
        metas = vector_results.get("metadatas", [])

        if not docs:
            return "", [], []

        settings = get_settings()
        max_context_chars = getattr(settings, "MAX_CONTEXT_CHARS", MAX_CONTEXT_LENGTH)
        max_docs = getattr(settings, "MAX_DOCUMENTS_FOR_ANSWER", 10)

        sources: List[str] = []
        summaries: List[str] = []
        context_parts: List[str] = []
        current_length = 0

        for i, doc in enumerate(docs):
            if not doc or i >= max_docs:
                continue

            meta = metas[i] if i < len(metas) else None
            source_name = ""
            if meta and isinstance(meta, dict):
                # Prefer the extracted document title (from the converted markdown)
                # over the raw filename, which may be a placeholder name.
                src = (
                    meta.get("title")
                    or meta.get("file_name")
                    or meta.get("parent_doc")
                    or meta.get("source")
                    or ""
                )
                if src:
                    source_name = CitationManager.clean_source_name(src) or src
                    if source_name and source_name not in sources:
                        sources.append(source_name)
                if meta.get("summary"):
                    summaries.append(meta["summary"])

            # Wrap the chunk with a source label and 1-indexed citation number
            # so the LLM can cite with [cite_kb: N] instead of raw source names.
            tag_name = html.escape(source_name or f"Document {i + 1}", quote=True)
            source_index = (sources.index(source_name) + 1) if source_name in sources else (i + 1)
            wrapped = f"<source index=\"{source_index}\" name=\"{tag_name}\">\n{doc}\n</source>"
            wrapped_len = len(wrapped)

            if current_length + wrapped_len > max_context_chars:
                remaining = max_context_chars - current_length
                if remaining > 100:
                    truncated = wrapped[:remaining]
                    last_para = truncated.rfind("\n\n")
                    if last_para > 0:
                        context_parts.append(wrapped[:last_para])
                    else:
                        for punct in [".", "!", "?"]:
                            last_punct = truncated.rfind(punct)
                            if last_punct > 0 and last_punct + 1 < len(truncated) and truncated[last_punct + 1].isspace():
                                context_parts.append(wrapped[:last_punct + 1])
                                break
                        else:
                            context_parts.append(wrapped[:remaining])
                break

            context_parts.append(wrapped)
            current_length += wrapped_len

        full_context = "\n\n".join(context_parts)
        return full_context, summaries, sources

    @staticmethod
    def _build_context_fingerprint(
        context_text: str, summaries: List[str], sources: List[str]
    ) -> str:
        """Build a stable fingerprint for the retrieval context."""
        payload = {
            "context": context_text,
            "summaries": summaries,
            "sources": sources,
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

    def _sanitize_query(self, query: str) -> tuple[str, bool]:
        """Detect and sanitize potential prompt injection attempts."""
        prompt_guard = get_prompt_guard()
        try:
            sanitized_query = prompt_guard.sanitize_query(query)
            return sanitized_query, False
        except PromptInjectionError as e:
            logger.warning(
                f"Prompt injection detected by guard: hash={e.query_hash}, "
                f"confidence={e.confidence}, method={e.method}"
            )
            return query, True
