"""OpenAI-compatible LLM client.

Works with any provider that exposes the OpenAI Chat Completions API:
- OpenAI (api.openai.com)
- Ollama (localhost:11434/v1)
- OpenRouter (openrouter.ai/api/v1)
- Groq, Together, vLLM, LM Studio, etc.
"""

from typing import Dict, Any, Optional, Tuple, AsyncIterator
from tenacity import AsyncRetrying, stop_after_attempt, wait_random_exponential, retry_if_exception

from ..api.middleware.circuit_breaker import get_circuit_breaker, CircuitConfig
from .base_rag_client import BaseRAGClient


class OpenAIProcessingError(Exception):
    """Exception raised during OpenAI-compatible processing."""
    pass


class OpenAICompatibleClient(BaseRAGClient):
    """LLM client for any OpenAI-compatible API.

    Covers OpenAI, Ollama, OpenRouter, Groq, Together, vLLM, LM Studio, etc.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model_main: str = "gpt-4.1-mini",
        model_lite: Optional[str] = None,
        model_relevance: Optional[str] = None,
        organization: Optional[str] = None,
    ):
        """Initialize the OpenAI-compatible client.

        Args:
            api_key: API key for the provider. For Ollama, use any non-empty string.
            base_url: Base URL for the API. Must end with /v1 for OpenAI-compatible endpoints.
            model_main: Primary model name for answer generation.
            model_lite: Lite model for low-latency tasks. Defaults to model_main.
            model_relevance: Model for post-generation relevance check. Defaults to model_lite.
            organization: OpenAI organization ID (optional, OpenAI only).
        """
        super().__init__()
        # Lazy import — the openai SDK may not be installed if only using Gemini
        try:
            from openai import AsyncOpenAI
        except ImportError as e:
            raise ImportError(
                "The 'openai' package is required for OpenAI-compatible providers. "
                "Install it with: pip install openai"
            ) from e

        self._model_main = model_main
        self._model_lite = model_lite or model_main
        self._model_relevance = model_relevance or self._model_lite
        self._base_url = base_url

        client_kwargs: Dict[str, Any] = {
            "api_key": api_key,
            "base_url": base_url,
        }
        if organization:
            client_kwargs["organization"] = organization

        self.client = AsyncOpenAI(**client_kwargs)

        # Dedicated circuit breaker for this provider
        self._circuit = get_circuit_breaker(
            f"openai_compat_{base_url}",
            CircuitConfig(
                failure_threshold=3,
                timeout_seconds=60.0,
                success_threshold=2,
            ),
        )

    # ------------------------------------------------------------------
    # LLMClient interface properties
    # ------------------------------------------------------------------

    @property
    def model_main(self) -> str:
        return self._model_main

    @property
    def model_lite(self) -> str:
        return self._model_lite

    @property
    def model_relevance(self) -> str:
        return self._model_relevance

    # ------------------------------------------------------------------
    # LLMClient interface methods
    # ------------------------------------------------------------------

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
        """Generate text from a prompt via OpenAI Chat Completions API."""
        resolved_model = model or self._model_main

        kwargs: Dict[str, Any] = {
            "model": resolved_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "top_p": top_p,
        }
        if max_output_tokens is not None:
            kwargs["max_tokens"] = max_output_tokens
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        async def _call():
            if self._circuit:
                response = await self._circuit.call(
                    self.client.chat.completions.create, **kwargs
                )
            else:
                response = await self.client.chat.completions.create(**kwargs)
            return response

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_random_exponential(multiplier=1, max=8),
            retry=retry_if_exception(self._is_retryable_error),
            reraise=True,
        ):
            with attempt:
                response = await _call()
                return response.choices[0].message.content or ""

    async def generate_text_stream(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
        top_p: float = 0.9,
    ) -> AsyncIterator[str]:
        """Stream text chunks from a prompt via OpenAI streaming."""
        resolved_model = model or self._model_main

        if self._circuit and not await self._circuit.can_execute():
            raise OpenAIProcessingError("Circuit is open")

        kwargs: Dict[str, Any] = {
            "model": resolved_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "top_p": top_p,
            "stream": True,
        }

        stream_error = None
        try:
            stream = await self.client.chat.completions.create(**kwargs)
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            stream_error = e
            raise OpenAIProcessingError(f"Streaming error: {e}") from e
        finally:
            if self._circuit:
                if stream_error is None:
                    self._circuit.record_success()
                else:
                    self._circuit.record_failure(stream_error)

    async def _generate_for_rag(self, prompt: str) -> Tuple[str, Dict[str, int]]:
        """Generate answer text for the RAG pipeline.

        The prompt already includes the system instruction (prepended by
        BaseRAGClient.search_and_process).
        """
        kwargs: Dict[str, Any] = {
            "model": self._model_main,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "top_p": 0.9,
        }

        async def _call():
            if self._circuit:
                return await self._circuit.call(
                    self.client.chat.completions.create, **kwargs
                )
            return await self.client.chat.completions.create(**kwargs)

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_random_exponential(multiplier=1, max=8),
            retry=retry_if_exception(self._is_retryable_error),
            reraise=True,
        ):
            with attempt:
                response = await _call()
                answer_text = response.choices[0].message.content or ""
                tokens_in = 0
                tokens_out = 0
                usage = getattr(response, "usage", None)
                if usage:
                    tokens_in = getattr(usage, "prompt_tokens", 0) or 0
                    tokens_out = getattr(usage, "completion_tokens", 0) or 0
                return answer_text, {"tokens_in": tokens_in, "tokens_out": tokens_out}

    # ------------------------------------------------------------------
    # Error classification
    # ------------------------------------------------------------------

    @staticmethod
    def _is_retryable_error(exception: Exception) -> bool:
        """Check if an error is retryable (transient/5xx)."""
        error_msg = str(exception)

        # 429 rate limits — retry with backoff
        if "429" in error_msg or "rate_limit" in error_msg.lower():
            return True

        # 5xx server errors — retry
        if any(code in error_msg for code in ["500", "502", "503", "504"]):
            return True

        # Timeout / connection errors
        if "timeout" in error_msg.lower() or "connection" in error_msg.lower():
            return True

        # OpenAI SDK specific: APIStatusError with 5xx status
        status_code = getattr(exception, "status_code", None)
        if status_code is not None and 500 <= status_code < 600:
            return True

        return False

    def get_status(self) -> Dict[str, Any]:
        """Get client status for monitoring."""
        return {
            "model": self._model_main,
            "model_lite": self._model_lite,
            "base_url": self._base_url,
        }
