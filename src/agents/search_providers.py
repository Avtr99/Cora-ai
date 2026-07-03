"""Search provider abstraction for pluggable web search backends."""

from typing import List, Optional


class SearchResult:
    def __init__(
        self,
        id: str,
        title: str,
        url: str,
        content: str,
        score: Optional[float] = None,
        published_date: Optional[str] = None,
    ):
        self.id = id
        self.title = title
        self.url = url
        self.content = content
        self.score = score
        self.published_date = published_date


class SearchProvider:
    """Abstract base for web search providers.

    Implementations must provide an async ``search`` method returning a list
    of ``SearchResult`` objects.
    """

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Perform a web search and return a list of SearchResult objects."""
        raise NotImplementedError
