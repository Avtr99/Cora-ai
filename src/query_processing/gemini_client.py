"""Async Gemini client for the Cora RAG backend.

Optimizations:
- True ASYNC generation using client.aio to prevent blocking the event loop
- Removed explicit context caching (system prompts are too small to justify storage costs)
- Token usage metadata for monitoring
"""

from google import genai
from google.genai import types
from google.genai import errors
from typing import Dict, Any, Optional, Tuple, AsyncIterator
import re
from tenacity import AsyncRetrying, stop_after_attempt, wait_random_exponential, retry_if_exception
from loguru import logger

from ..config import get_settings
from ..api.middleware.circuit_breaker import gemini_circuit
from .prompts import (
    VCM_SYSTEM_INSTRUCTION,
    _today_utc,
)
from .base_rag_client import BaseRAGClient

class GeminiProcessingError(Exception):
    """Exception raised during Gemini processing with preserved traceback."""
    pass

class GeminiClient(BaseRAGClient):
    """
    Async Gemini client.

    Uses true async generation (client.aio) to handle concurrent requests
    efficiently without blocking the event loop.
    """
    
    _instance: Optional['GeminiClient'] = None

    @property
    def model_name(self) -> str:
        """Get the main model name for answer generation (higher accuracy)."""
        settings = get_settings()
        return getattr(settings, "GEMINI_MODEL_MAIN", "gemini-2.5-flash")

    @property
    def model_main(self) -> str:
        """LLMClient interface — alias for model_name."""
        return self.model_name

    @property
    def model_lite(self) -> str:
        """LLMClient interface — lite model for low-latency tasks."""
        settings = get_settings()
        return getattr(settings, "GEMINI_MODEL_LITE", "gemini-2.5-flash-lite")

    @property
    def model_relevance(self) -> str:
        """LLMClient interface — model for post-generation relevance check."""
        return self._model_relevance or self.model_lite

    @property
    def model_name_lite(self) -> str:
        """Legacy alias for model_lite (backwards compatibility)."""
        return self.model_lite

    def __init__(self, api_key: Optional[str] = None, model_relevance: Optional[str] = None):
        """
        Initialize Gemini client with API key authentication.
        """
        super().__init__()
        self._api_key = api_key
        self._model_relevance = model_relevance
        self._initialize_client()

        # Generation config optimized for factual RAG responses
        self.generation_config = types.GenerateContentConfig(
            temperature=0.3,
            top_p=0.9,
            top_k=50,
            candidate_count=1,
        )

    def _initialize_client(self):
        """Initialize the genai client using Gemini API key."""
        settings = get_settings()
        http_options = types.HttpOptions(
            retry_options=types.HttpRetryOptions(
                attempts=3,
                initial_delay=1.0,
                max_delay=8.0,
                exp_base=2.0,
                jitter=True,
                http_status_codes=[429, 500, 502, 503, 504],
            )
        )

        api_key = self._api_key or settings.GEMINI_API_KEY
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required")

        self.client = genai.Client(
            api_key=api_key,
            http_options=http_options,
        )
        logger.info("Gemini client initialized")
        
    # Pre-compiled regex for word-boundary numeric code matching (avoids false positives on ports/IDs)
    _RETRYABLE_CODE_REGEX = re.compile(r'\b(?:500|502|503|504)\b')

    @staticmethod
    def _is_retryable_error(exception: Exception) -> bool:
        """Check if an exception is retryable.

        429 / RESOURCE_EXHAUSTED is NOT retryable — retrying while over quota
        makes the problem worse. The caller should fail fast and let upstream
        circuit-breakers or backpressure handle it.
        """
        if isinstance(exception, errors.APIError):
            return exception.code in {500, 502, 503, 504}
        error_msg = str(exception).upper()
        # Use word-boundary matching for numeric codes to avoid matching port numbers or IDs
        return (
            bool(GeminiClient._RETRYABLE_CODE_REGEX.search(error_msg))
            or "INTERNAL" in error_msg
            or "UNAVAILABLE" in error_msg
        )

    async def generate(self, prompt: str):
        """Generate content from a prompt with bounded retries.

        Public API for callers that need raw Gemini generation without
        the full search-and-process pipeline (e.g. summarization).

        **Trust boundary:** This method does NOT perform input validation
        (length checks, sanitization, or injection detection) because it
        is intended only for internally-constructed prompts where the
        caller controls the content. External/user-facing inputs MUST go
        through ``search_and_process`` which enforces MAX_QUERY_LENGTH
        and ``_sanitize_query`` checks. Do NOT pass raw user input here.

        Args:
            prompt: The prompt string to send to the model.

        Returns:
            GenerateContentResponse from the Gemini API.
        """
        return await self._generate_with_retry(prompt)

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
        """Generate text from a prompt (LLMClient interface).

        This is the unified method used by all agents (router, rewriter,
        validator, conversational handler, web search). It handles:
        - Per-call generation config (temperature, top_p, json_mode)
        - Circuit breaker protection via ``gemini_circuit``
        - Retry with exponential backoff for transient failures

        Unlike ``generate()`` / ``_generate_async()``, this method does NOT
        prepend the VCM system instruction — agents build their own prompts
        with the necessary context. The system instruction is only prepended
        in the ``search_and_process`` answer-generation path.

        Args:
            prompt: The prompt string to send to the model.
            model: Model name override. Defaults to ``self.model_name``.
            temperature: Sampling temperature (0.0-2.0).
            top_p: Nucleus sampling parameter.
            max_output_tokens: Maximum tokens to generate. None = provider default.
            json_mode: If True, force JSON-formatted output.

        Returns:
            The generated text string.
        """
        resolved_model = model or self.model_name

        config_kwargs: Dict[str, Any] = {
            "temperature": temperature,
            "top_p": top_p,
            "candidate_count": 1,
        }
        if max_output_tokens is not None:
            config_kwargs["max_output_tokens"] = max_output_tokens
        if json_mode:
            config_kwargs["response_mime_type"] = "application/json"

        call_config = types.GenerateContentConfig(**config_kwargs)

        async def _call():
            if gemini_circuit:
                return await gemini_circuit.call(
                    self.client.aio.models.generate_content,
                    model=resolved_model,
                    contents=prompt,
                    config=call_config,
                )
            return await self.client.aio.models.generate_content(
                model=resolved_model,
                contents=prompt,
                config=call_config,
            )

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_random_exponential(multiplier=1, max=8),
            retry=retry_if_exception(self._is_retryable_error),
            reraise=True,
        ):
            with attempt:
                response = await _call()
                return self._extract_response_text(response)

    async def generate_text_stream(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
        top_p: float = 0.9,
    ) -> AsyncIterator[str]:
        """Stream text chunks from a prompt (LLMClient interface).

        Unlike ``GeminiStreamingClient.generate_stream()``, this does NOT
        prepend the VCM system instruction — callers build their own prompts.

        Yields:
            Text chunks as they arrive from the model.
        """
        resolved_model = model or self.model_name
        call_config = types.GenerateContentConfig(
            temperature=temperature,
            top_p=top_p,
            candidate_count=1,
        )

        if not await gemini_circuit.can_execute():
            raise GeminiProcessingError("Gemini circuit is open")

        stream = None
        stream_error = None
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_random_exponential(multiplier=1, max=8),
                retry=retry_if_exception(self._is_retryable_error),
                reraise=True,
            ):
                with attempt:
                    stream = await self.client.aio.models.generate_content_stream(
                        model=resolved_model,
                        contents=prompt,
                        config=call_config,
                    )
                    break

            async for chunk in stream:
                text = self._extract_text_from_chunk(chunk) if hasattr(self, "_extract_text_from_chunk") else None
                if text is None:
                    text = getattr(chunk, "text", None)
                if text:
                    yield text
        except Exception as e:
            stream_error = e
            raise GeminiProcessingError(f"Gemini streaming error: {e}") from e
        finally:
            if stream_error is None:
                gemini_circuit.record_success()
            else:
                gemini_circuit.record_failure(stream_error)

    def extract_response_text(self, response: Any) -> str:
        """Safely extract answer text from a Gemini response.

        Public API wrapping the internal extraction logic so callers
        do not need to access private methods.

        Args:
            response: GenerateContentResponse from the Gemini API.

        Returns:
            Extracted text string.
        """
        return self._extract_response_text(response)

    async def _generate_with_retry(self, prompt: str):
        """Generate content with bounded retries for transient provider failures."""
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_random_exponential(multiplier=1, max=8),
            retry=retry_if_exception(self._is_retryable_error),
            reraise=True,
        ):
            with attempt:
                return await self._generate_async(prompt)

    # check_query_cache, persist_to_l2, and search_and_process are inherited
    # from BaseRAGClient (provider-agnostic implementations).

    async def _generate_async(self, prompt: str):
        """
        Generate content using true async API.
        
        Uses client.aio.models.generate_content for non-blocking execution.
        System instruction is included in the prompt (stateless, no explicit cache).
        
        Args:
            prompt: The user prompt to process
            
        Returns:
            GenerateContentResponse object
        """
        # Include system instruction in prompt (stateless approach)
        # Substitute {current_date} placeholder for temporal awareness
        formatted_instruction = VCM_SYSTEM_INSTRUCTION.replace("{current_date}", _today_utc())
        full_prompt = f"{formatted_instruction}\n\n{prompt}"
        
        response = await gemini_circuit.call(
            self.client.aio.models.generate_content,
            model=self.model_name,
            contents=full_prompt,
            config=self.generation_config,
        )

        return response

    async def _generate_for_rag(self, prompt: str) -> Tuple[str, Dict[str, int]]:
        """Generate answer text for the RAG pipeline (BaseRAGClient interface).

        The prompt already includes the system instruction (prepended by
        ``BaseRAGClient.search_and_process``). We call the Gemini API with
        retries and circuit breaker, then extract text + token usage.

        Args:
            prompt: Full prompt (system instruction + context + query).

        Returns:
            Tuple of (answer_text, usage_dict).
        """
        response = await self._generate_with_retry_raw(prompt)
        answer_text = self._extract_response_text(response)

        tokens_in = 0
        tokens_out = 0
        usage_metadata = getattr(response, "usage_metadata", None)
        if usage_metadata:
            tokens_in = getattr(usage_metadata, "prompt_token_count", 0) or 0
            tokens_out = getattr(usage_metadata, "candidates_token_count", 0) or 0

        return answer_text, {"tokens_in": tokens_in, "tokens_out": tokens_out}

    async def _generate_with_retry_raw(self, prompt: str):
        """Generate content with retries, WITHOUT prepending system instruction.

        Unlike ``_generate_with_retry`` → ``_generate_async``, this does NOT
        prepend the VCM system instruction — the caller (``_generate_for_rag``)
        receives a prompt that already has it prepended by the base class.
        """
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_random_exponential(multiplier=1, max=8),
            retry=retry_if_exception(self._is_retryable_error),
            reraise=True,
        ):
            with attempt:
                if gemini_circuit:
                    return await gemini_circuit.call(
                        self.client.aio.models.generate_content,
                        model=self.model_name,
                        contents=prompt,
                        config=self.generation_config,
                    )
                return await self.client.aio.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=self.generation_config,
                )

    def _extract_response_text(self, response: Any) -> str:
        """Safely extract answer text from a Gemini response.

        Handles SDK cases where ``response.text`` raises when no direct text is
        available by falling back to candidate content parts.
        """
        fallback_text = "I could not generate an answer based on the retrieved documents."

        try:
            text = getattr(response, "text", None)
            if isinstance(text, str) and text.strip():
                return text
        except (AttributeError, ValueError, TypeError) as text_error:
            logger.warning(f"Could not extract response.text directly: {text_error}")

        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) if content else None
            if not parts:
                continue

            part_texts = []
            for part in parts:
                part_text = getattr(part, "text", None)
                if isinstance(part_text, str):
                    text = part_text.strip()
                    if text:
                        part_texts.append(text)
            if part_texts:
                return "\n".join(part_texts)

        return fallback_text

    # _prepare_context, _build_context_fingerprint, _should_cache_answer,
    # _calculate_coverage_score, and _sanitize_query are inherited from
    # BaseRAGClient (provider-agnostic implementations).

    def get_status(self) -> Dict[str, Any]:
        """
        Get client status for monitoring.

        Returns:
            Dictionary with client status information
        """
        return {
            "model": self.model_name,
            "model_lite": self.model_name_lite,
        }