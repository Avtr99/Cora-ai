"""Shared agent protocols.

Centralises runtime-checkable protocols used by route handlers and the
orchestrator so they are defined once and imported consistently.
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class RetrieverProtocol(Protocol):
    """Protocol for retriever implementations."""

    async def retrieve(
        self,
        query: str,
        where: Optional[Dict[str, Any]] = None,
        allow_unfiltered_fallback: bool = False,
        original_query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve documents matching the query."""
        ...


@runtime_checkable
class FusionRetrieverProtocol(RetrieverProtocol, Protocol):
    """Protocol for retrievers supporting multi-query fusion retrieval."""

    async def retrieve_with_fusion(
        self,
        query: str,
        sub_queries: List[str],
        where: Optional[Dict[str, Any]] = None,
        allow_unfiltered_fallback: bool = False,
        original_query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve documents using multiple sub-queries."""
        ...


@runtime_checkable
class AnswerGeneratorProtocol(Protocol):
    """Protocol for answer generator implementations."""

    async def search_and_process(self, query: str, vector_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate an answer from retrieved documents."""
        ...

    async def check_query_cache(self, query: str) -> Optional[Dict[str, Any]]:
        """Check in-memory and SQLite caches for a query-only cached answer."""
        ...


@runtime_checkable
class RelevanceCheckerProtocol(Protocol):
    """Protocol for relevance checker implementations."""

    async def check_relevance(
        self,
        query: str,
        answer: str,
        source_titles: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Check whether an answer is relevant to the query."""
        ...


@runtime_checkable
class WebSearchProtocol(Protocol):
    """Protocol for web search implementations."""

    async def search(
        self,
        query: str,
        context: str = "",
        timeout_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Perform web search and return results."""
        ...

    async def search_with_kb_context(
        self,
        query: str,
        kb_context: str,
        kb_sources: List[str],
        timeout_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Search with knowledge base context."""
        ...


@runtime_checkable
class ConfigProtocol(Protocol):
    """Protocol for orchestrator config."""

    enable_web_search: bool
    retrieval_threshold: float
    retrieval_k: int
