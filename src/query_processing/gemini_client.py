"""Async Gemini client for the Cora RAG backend.

Optimizations:
- True ASYNC generation using client.aio to prevent blocking the event loop
- Removed explicit context caching (system prompts are too small to justify storage costs)
- Token usage metadata for monitoring
"""

from google import genai
from google.genai import types
from typing import Dict, Any, Optional, Tuple, AsyncIterator
from loguru import logger

from ..config import get_settings
from ..api.middleware.circuit_breaker import gemini_circuit
from ..utils.gemini_config import build_generate_content_config, is_retired_model, _bare_model
from .fallback_answers import GENERATION_FAILED_ANSWER
from .prompts import (
    get_system_instruction,
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

    @staticmethod
    def _is_valid_model(model: Optional[str]) -> bool:
        """Check if a model name is a valid Gemini API identifier.

        Accepts either a short ID (``gemini-2.5-flash``) or a full resource
        path (``models/gemini-2.5-flash`` / ``tunedModels/...``). Anything
        with another provider prefix (e.g. ``google/gemini-2.5-flash``) or
        a non-Gemini name is rejected.
        """
        if not model:
            return False
        if "/" in model:
            prefix, _, suffix = model.partition("/")
            if prefix == "tunedModels":
                return True
            return (
                prefix == "models"
                and suffix.startswith("gemini-")
                and not is_retired_model(suffix)
            )
        return model.startswith("gemini-") and not is_retired_model(model)

    @property
    def model_name(self) -> str:
        """Get the main model name for answer generation (higher accuracy).

        Uses the DB/UI-supplied model if available, otherwise falls back to
        the env default. This keeps the cache-invalidation fingerprint and the
        actual generation model in sync.
        """
        if self._model_main and self._is_valid_model(self._model_main):
            return self._model_main
        if self._model_main:
            logger.warning(
                f"Configured Gemini model {self._model_main!r} is not a valid "
                f"Gemini model ID; falling back to env default."
            )
        settings = get_settings()
        return getattr(settings, "GEMINI_MODEL_MAIN", "gemini-3.8-flash")

    @property
    def circuit(self):
        """LLMClient interface — shared Gemini circuit breaker."""
        return gemini_circuit

    @property
    def model_main(self) -> str:
        """LLMClient interface — alias for model_name."""
        return self.model_name

    @property
    def model_lite(self) -> str:
        """LLMClient interface — lite model for low-latency tasks."""
        if self._model_lite and self._is_valid_model(self._model_lite):
            return self._model_lite
        if self._model_lite:
            logger.warning(
                f"Configured Gemini lite model {self._model_lite!r} is not a "
                f"valid Gemini model ID; falling back to env default."
            )
        settings = get_settings()
        return getattr(settings, "GEMINI_MODEL_LITE", "gemini-3.5-flash-lite")

    @property
    def model_relevance(self) -> str:
        """LLMClient interface — model for post-generation relevance check."""
        if self._model_relevance and self._is_valid_model(self._model_relevance):
            return self._model_relevance
        if self._model_relevance:
            logger.warning(
                f"Configured Gemini relevance model {self._model_relevance!r} is "
                f"not a valid Gemini model ID; falling back to lite model."
            )
        return self.model_lite

    @property
    def model_name_lite(self) -> str:
        """Legacy alias for model_lite (backwards compatibility)."""
        return self.model_lite

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_main: Optional[str] = None,
        model_lite: Optional[str] = None,
        model_relevance: Optional[str] = None,
    ):
        """
        Initialize Gemini client with API key authentication.
        """
        super().__init__()
        self._api_key = api_key
        self._model_main = model_main
        self._model_lite = model_lite
        self._model_relevance = model_relevance
        self._initialize_client()

    @property
    def generation_config(self) -> types.GenerateContentConfig:
        """Generation config for the main model, built on demand.

        Lazily built so a retired configured model surfaces the clear
        ``build_generate_content_config`` error at request time rather than
        during client construction. gemini-3.x takes a ``ThinkingConfig``
        instead of temperature/top_p/top_k.
        """
        return build_generate_content_config(
            self.model_name,
            thinking_level=get_settings().GEMINI_THINKING_LEVEL,
        )

    def _thinking_level_for(self, model_name: str) -> Optional[str]:
        """Pick the configured thinking level for a resolved model.

        Lite and relevance models use ``GEMINI_THINKING_LEVEL_LITE``; the main
        model uses ``GEMINI_THINKING_LEVEL``. Main is checked first: when the
        same model serves both tiers, the main level wins — the lite level may
        be MINIMAL, which the main model can reject.
        """
        settings = get_settings()
        bare = _bare_model(model_name)
        if bare == _bare_model(self.model_name):
            return settings.GEMINI_THINKING_LEVEL
        if bare in (
            _bare_model(self.model_lite),
            _bare_model(self.model_relevance),
        ):
            return settings.GEMINI_THINKING_LEVEL_LITE
        return settings.GEMINI_THINKING_LEVEL

    def _initialize_client(self):
        """Initialize the genai client using Gemini API key."""
        settings = get_settings()
        # Single retry layer: the SDK retries matching status codes plus
        # transient httpx errors. 429/RESOURCE_EXHAUSTED is excluded —
        # retrying while over quota makes the problem worse, so it fails
        # fast and lets the circuit breaker handle backpressure.
        http_options = types.HttpOptions(
            retry_options=types.HttpRetryOptions(
                attempts=3,
                initial_delay=1.0,
                max_delay=8.0,
                exp_base=2.0,
                jitter=True,
                http_status_codes=[500, 502, 503, 504],
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

    async def generate(self, prompt: str):
        """Generate content from a prompt.

        Public API for callers that need raw Gemini generation without
        the full search-and-process pipeline (e.g. summarization).
        Transient-failure retries are handled inside the SDK (see
        ``_initialize_client``).

        **Trust boundary:** This method does NOT perform input validation
        (length checks, sanitization, or injection detection) because it
        is intended only for internally-constructed prompts where the
        caller controls the content. External/user-facing inputs MUST go
        through ``search_and_process`` which enforces MAX_QUERY_LENGTH,
        and through the API-layer input sanitizer. Do NOT pass raw user
        input here.

        Args:
            prompt: The prompt string to send to the model.

        Returns:
            GenerateContentResponse from the Gemini API.
        """
        return await self._generate_async(prompt)

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
        - Per-call generation config (json_mode, max_output_tokens, thinking level)
        - Circuit breaker protection via ``gemini_circuit``

        Unlike ``generate()`` / ``_generate_async()``, this method does NOT
        prepend the VCM system instruction — agents build their own prompts
        with the necessary context. The system instruction is only prepended
        in the ``search_and_process`` answer-generation path.

        Args:
            prompt: The prompt string to send to the model.
            model: Model name override. Defaults to ``self.model_name``.
            temperature: Ignored — gemini-3.x rejects sampling parameters.
                Reasoning effort is set via ``GEMINI_THINKING_LEVEL`` /
                ``GEMINI_THINKING_LEVEL_LITE`` instead.
            top_p: Ignored — see ``temperature``.
            max_output_tokens: Maximum tokens to generate. None = provider default.
            json_mode: If True, force JSON-formatted output.

        Returns:
            The generated text string.
        """
        resolved_model = model or self.model_name

        config_kwargs: Dict[str, Any] = {}
        if max_output_tokens is not None:
            config_kwargs["max_output_tokens"] = max_output_tokens
        if json_mode:
            config_kwargs["response_mime_type"] = "application/json"

        call_config = build_generate_content_config(
            resolved_model,
            thinking_level=self._thinking_level_for(resolved_model),
            **config_kwargs,
        )

        if gemini_circuit:
            response = await gemini_circuit.call(
                self.client.aio.models.generate_content,
                model=resolved_model,
                contents=prompt,
                config=call_config,
            )
        else:
            response = await self.client.aio.models.generate_content(
                model=resolved_model,
                contents=prompt,
                config=call_config,
            )
        return self._extract_response_text(response)

    async def generate_text_stream(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
        top_p: float = 0.9,
        usage_out: Optional[list] = None,
    ) -> AsyncIterator[str]:
        """Stream text chunks from a prompt (LLMClient interface).

        Does NOT prepend the VCM system instruction — callers build their
        own prompts.

        Args:
            prompt: The prompt string to send to the model.
            model: Model name override. Defaults to ``self.model_name``.
            temperature: Ignored — gemini-3.x rejects sampling parameters.
            top_p: Ignored — see ``temperature``.
            usage_out: Optional mutable list; the final chunk's usage is
                appended as a normalized ``{"tokens_in", "tokens_out"}`` dict
                (gemini-3.x thought tokens included in ``tokens_out``).

        Yields:
            Text chunks as they arrive from the model.
        """
        resolved_model = model or self.model_name
        call_config = build_generate_content_config(
            resolved_model,
            thinking_level=self._thinking_level_for(resolved_model),
        )

        if not await gemini_circuit.can_execute():
            raise GeminiProcessingError("Gemini circuit is open")

        stream = None
        stream_error = None
        try:
            stream = await self.client.aio.models.generate_content_stream(
                model=resolved_model,
                contents=prompt,
                config=call_config,
            )

            async for chunk in stream:
                usage = getattr(chunk, "usage_metadata", None)
                if usage is not None and usage_out is not None:
                    usage_out.clear()
                    usage_out.append({
                        "tokens_in": getattr(usage, "prompt_token_count", 0) or 0,
                        # gemini-3.x bills thoughts_token_count at the output rate.
                        "tokens_out": (
                            (getattr(usage, "candidates_token_count", 0) or 0)
                            + (getattr(usage, "thoughts_token_count", 0) or 0)
                        ),
                    })
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

    # check_query_cache, persist_to_cache, and search_and_process are inherited
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
        formatted_instruction = get_system_instruction().replace("{current_date}", _today_utc())
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
        response = await self._generate_raw(prompt)
        answer_text = self._extract_response_text(response)

        tokens_in = 0
        tokens_out = 0
        usage_metadata = getattr(response, "usage_metadata", None)
        if usage_metadata:
            tokens_in = getattr(usage_metadata, "prompt_token_count", 0) or 0
            # gemini-3.x bills thoughts_token_count at the output rate.
            tokens_out = (
                (getattr(usage_metadata, "candidates_token_count", 0) or 0)
                + (getattr(usage_metadata, "thoughts_token_count", 0) or 0)
            )

        return answer_text, {"tokens_in": tokens_in, "tokens_out": tokens_out}

    async def _generate_raw(self, prompt: str):
        """Generate content WITHOUT prepending system instruction.

        Unlike ``_generate_async``, this does NOT prepend the VCM system
        instruction — the caller (``_generate_for_rag``) receives a prompt
        that already has it prepended by the base class. Retries are handled
        inside the SDK (see ``_initialize_client``).
        """
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
        fallback_text = GENERATION_FAILED_ANSWER

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

    # _build_context_fingerprint, _should_cache_answer, and
    # _calculate_coverage_score are inherited from BaseRAGClient
    # (provider-agnostic implementations).

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