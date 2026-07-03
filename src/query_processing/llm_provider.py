"""LLM provider abstraction layer.

Defines the unified interface that all LLM clients (Gemini, OpenAI-compatible)
implement. Agents call ``generate_text()`` without knowing which provider is
active.
"""

from typing import Protocol, AsyncIterator, Optional, Any, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    """Unified interface for LLM generation across providers.

    Implementations:
    - GeminiClient (via google-genai SDK)
    - OpenAICompatibleClient (via openai SDK — covers OpenAI, Ollama, OpenRouter, etc.)
    """

    @property
    def model_main(self) -> str:
        """Primary model name for answer generation."""
        ...

    @property
    def model_lite(self) -> str:
        """Lite model name for low-latency tasks (routing, classification).

        For providers that don't have a separate lite model, this returns the
        same value as ``model_main``.
        """
        ...

    @property
    def model_relevance(self) -> str:
        """Model name for the post-generation relevance check.

        Defaults to ``model_lite``; for providers without a dedicated lite model
        this is typically the same as ``model_main``.
        """
        ...

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
        """Generate text from a prompt.

        This is the primary method used by agents (router, rewriter, validator,
        conversational handler, web search). It handles:
        - Provider-specific request formatting (Gemini contents vs OpenAI messages)
        - Circuit breaker protection
        - Retry with exponential backoff for transient failures

        Args:
            prompt: The prompt string to send to the model.
            model: Model name override. Defaults to ``self.model_main``.
            temperature: Sampling temperature (0.0-2.0).
            top_p: Nucleus sampling parameter.
            max_output_tokens: Maximum tokens to generate. None = provider default.
            json_mode: If True, force JSON-formatted output.

        Returns:
            The generated text string.

        Raises:
            Exception: If generation fails after retries.
        """
        ...

    async def generate_text_stream(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
        top_p: float = 0.9,
    ) -> AsyncIterator[str]:
        """Stream text chunks from a prompt.

        Used by the streaming orchestrator for real-time token delivery.

        Args:
            prompt: The prompt string to send to the model.
            model: Model name override. Defaults to ``self.model_main``.
            temperature: Sampling temperature.
            top_p: Nucleus sampling parameter.

        Yields:
            Text chunks as they arrive from the model.
        """
        ...

    async def search_and_process(
        self,
        query: str,
        vector_results: Any,
    ) -> dict:
        """Full RAG pipeline: build prompt with context, generate, extract citations.

        This is the high-level method used by route handlers. It:
        1. Sanitizes the query (prompt injection detection)
        2. Builds the RAG prompt with retrieved context
        3. Generates the answer
        4. Extracts citations
        5. Optionally generates quiz / suggested prompts

        Args:
            query: User query string.
            vector_results: Retrieved documents from the vector store.

        Returns:
            Result dict with answer, sources, citations, metadata.
        """
        ...
