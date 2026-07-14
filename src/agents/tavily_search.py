"""Tavily Search provider.

Implements the Tavily REST API (POST https://api.tavily.com/search) per the
official documentation: https://docs.tavily.com/documentation/api-reference/endpoint/search

Authentication uses the ``Authorization: Bearer tvly-KEY`` header (not the
deprecated ``api_key``-in-body approach).
"""

import logging
import re
from typing import List, Optional

import httpx

from ..config import get_settings
from .search_providers import SearchProvider, SearchResult

logger = logging.getLogger(__name__)

# Official endpoint — https://docs.tavily.com/documentation/api-reference/introduction
_TAVILY_SEARCH_URL = "https://api.tavily.com/search"
_TAVILY_TIMEOUT = 30.0  # seconds — Tavily advanced can take ~5-10s

# Search engines (including Tavily) prepend file-type markers to result titles for
# PDF/DOC/WEB links. Strip them before the title is used for citations or LLM context.
_SEARCH_PREFIX_RE = re.compile(r"^\[(?:PDF|DOC|WEB)\]\s*:?\s*", re.IGNORECASE)


def _strip_search_prefix(title: str) -> str:
    """Remove file-type prefixes like '[PDF] ' or '[PDF]: ' from search titles."""
    return _SEARCH_PREFIX_RE.sub("", title).strip()


class TavilySearchProvider(SearchProvider):
    """Tavily web search provider using the official REST API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        search_depth: str = "advanced",
        topic: str = "general",
    ):
        self.api_key = api_key or get_settings().TAVILY_API_KEY
        self.search_depth = search_depth
        self.topic = topic
        if not self.api_key:
            logger.warning("TAVILY_API_KEY is not set. Web search will fail if invoked.")

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        if not self.api_key:
            return []

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "query": query,
                "search_depth": self.search_depth,
                "topic": self.topic,
                "include_answer": False,
                "include_images": False,
                "include_raw_content": False,
                "max_results": max_results,
            }

            async with httpx.AsyncClient(timeout=_TAVILY_TIMEOUT) as client:
                response = await client.post(
                    _TAVILY_SEARCH_URL,
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            results: List[SearchResult] = []
            for i, res in enumerate(data.get("results", [])):
                results.append(SearchResult(
                    id=f"source_{i + 1}",
                    title=_strip_search_prefix(res.get("title", "")),
                    url=res.get("url", ""),
                    content=res.get("content", ""),
                    score=res.get("score"),
                    published_date=res.get("published_date"),
                ))
            return results

        except httpx.HTTPStatusError as e:
            logger.error(
                "Tavily search failed: HTTP %s — %s",
                e.response.status_code,
                e.response.text[:200] if e.response.text else "",
            )
            return []
        except Exception as e:
            logger.error("Tavily search failed: %s", e)
            return []
