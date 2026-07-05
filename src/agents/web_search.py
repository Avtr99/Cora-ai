"""
Web Search Agent

Uses pluggable SearchProvider (default Tavily) and an LLM to answer web queries.
"""

import asyncio
import logging
import re
import copy
import json
import hashlib
from typing import Dict, Any, List, Optional
from cachetools import TTLCache

from .search_providers import SearchProvider
from .tavily_search import TavilySearchProvider

from ..query_processing.quiz_utils import (
    build_quiz_instruction,
    should_generate_quiz,
    split_answer_and_quiz,
)
from ..query_processing.suggested_prompts import (
    should_generate_suggested_prompts,
    split_answer_and_suggested_prompts,
    build_suggested_prompts_instruction,
)

logger = logging.getLogger(__name__)

def sanitize_text(text: str, max_length: int = 500) -> str:
    if not text:
        return ""
    sanitized = text
    # basic regexes ...
    sanitized = re.sub(r'<[^>]+>', '', sanitized)
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    return sanitized.strip()

def sanitize_query(query: str) -> str:
    return sanitize_text(query, max_length=500)

def sanitize_kb_context(kb_context: str) -> str:
    return sanitize_text(kb_context, max_length=2000)

def _kb_sources_to_dicts(kb_sources: List[str]) -> List[Dict[str, Any]]:
    return [{"title": s, "url": "", "snippet": "", "type": "knowledge_base"} for s in kb_sources]

def parse_citations(text: str, valid_source_ids: List[str]) -> str:
    """Validate and normalize web citations to a single [Web, cite: N] format.

    Handles:
      - legacy [source_X] / [source_X, source_Y] citations
      - raw [N] / [N, M] citations
      - bare [Web] markers (removed, as they are not rendered correctly)
      - KB citations [cite_kb: N] normalized to [Knowledge Base, cite: N]
    """
    if not text:
        return text

    def _normalize_kb_numbers(parts: List[str]) -> List[str]:
        out: List[str] = []
        for part in parts:
            part = part.strip()
            if part.isdigit() and int(part) >= 1:
                out.append(part)
        return out

    def _replace_kb_citation(match: re.Match) -> str:
        nums = _normalize_kb_numbers(match.group(1).split(","))
        return f"[Knowledge Base, cite: {', '.join(nums)}]" if nums else ""

    text = re.sub(
        r"\[cite_kb:\s*(\d+(?:,\s*\d+)*)\]",
        _replace_kb_citation,
        text,
        flags=re.IGNORECASE,
    )

    if valid_source_ids:
        source_index = {sid: str(i + 1) for i, sid in enumerate(valid_source_ids)}
        valid_set = set(valid_source_ids)
        max_index = len(valid_source_ids)

        def _normalize_numbers(parts: List[str]) -> List[str]:
            out: List[str] = []
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                if part in valid_set:
                    out.append(source_index[part])
                elif part.isdigit() and 1 <= int(part) <= max_index:
                    out.append(part)
            return out

        def _replace_citation(match: re.Match) -> str:
            nums = _normalize_numbers(match.group(1).split(","))
            return f"[Web, cite: {', '.join(nums)}]" if nums else ""

        text = re.sub(
            r"\[(source_\d+(?:,\s*source_\d+)*)\]",
            _replace_citation,
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"\[(\d+(?:,\s*\d+)*)\]", _replace_citation, text)

    # Drop bare [Web] / [Web, ...] markers that carry no valid citation numbers.
    text = re.sub(r"\[Web(?:,\s*[^0-9\]]*)?\]", "", text, flags=re.IGNORECASE)

    # Clean up spacing/punctuation left by removed markers (mirrors citation_verifier).
    text = re.sub(r"  +", " ", text).strip()
    text = re.sub(r"\s+([.,;!?])", r"\1", text)
    return text


class WebSearchAgent:
    def __init__(self, llm_client, model_name: Optional[str] = None, search_provider: SearchProvider = None):
        """Initialize the WebSearchAgent.

        Args:
            llm_client: LLMClient instance used to generate text responses.
            model_name: Optional model name to pass to the LLM client. If None,
                the LLM client's default model is used.
            search_provider: Optional SearchProvider instance for web search.
                Defaults to TavilySearchProvider if not provided.
        """
        self.llm = llm_client
        self.model_name = model_name
        self.search_provider = search_provider or TavilySearchProvider()
        
        self._search_cache: TTLCache = TTLCache(maxsize=200, ttl=3600)
        self._timeout_cache: TTLCache = TTLCache(maxsize=100, ttl=120)

    @staticmethod
    def _cache_key(prefix: str, payload: Dict[str, Any]) -> str:
        normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
        return f"{prefix}:{digest}"

    def _get_cached(self, key: str) -> Dict[str, Any] | None:
        if key in self._search_cache:
            return copy.deepcopy(self._search_cache[key])
        if key in self._timeout_cache:
            return copy.deepcopy(self._timeout_cache[key])
        return None

    def _cache_result(self, key: str, result: Dict[str, Any]) -> None:
        # Don't cache error responses; the LLM may recover (e.g. quota reset),
        # and the fallback provider should be allowed to retry on the next call.
        if result.get("error"):
            return
        if result.get("timed_out"):
            self._timeout_cache[key] = copy.deepcopy(result)
            return
        self._search_cache[key] = copy.deepcopy(result)
    
    async def search(self, query: str, context: str = "", timeout_ms: int | None = None) -> Dict[str, Any]:
        cache_key = self._cache_key("web_search", {"query": (query or "").strip().lower(), "context": (context or "").strip().lower()})

        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            sanitized_query = sanitize_query(query)
            sanitized_context = sanitize_query(context) if context else ""

            # Fetch search results
            search_results = await self.search_provider.search(sanitized_query, max_results=5)
            
            web_sources = []
            valid_source_ids = []
            search_results_text = "<search_results>\n"
            for res in search_results:
                search_results_text += f"[{res.id}]\nTitle: {res.title}\nURL: {res.url}\nContent: {res.content}\n\n"
                web_sources.append({"title": res.title, "url": res.url, "snippet": res.content, "type": "web_search", "id": res.id})
                valid_source_ids.append(res.id)
            search_results_text += "</search_results>"
            
            include_quiz = should_generate_quiz(sanitized_query)
            quiz_instruction = build_quiz_instruction(include_quiz)
            include_suggested_prompts = should_generate_suggested_prompts(sanitized_query)
            suggested_prompts_instruction = build_suggested_prompts_instruction(include_suggested_prompts)
            
            prompt = f"""<system_role>
You are a helpful assistant with access to web search results.
</system_role>

<instructions>
1. Answer directly and authoritatively. NEVER use introductory phrases like 'Based on web results' or 'According to search.'
2. Rely entirely on the provided search results to answer the query.
3. Cite your sources using the [Web, cite: N] format where N is the source number from the search results (e.g., [Web, cite: 1]). Do NOT invent new sources.
4. Answer concisely for simple questions under 150 words.
5. When the user asks for detail, provide a structured answer using markdown headers and bullet points up to 300-500 words.
6. {quiz_instruction}
7. {suggested_prompts_instruction}
</instructions>

{search_results_text}

<reference_data>
{sanitized_context}
</reference_data>

<user_query>
{sanitized_query}
</user_query>"""
            
            raw_text = await self.llm.generate_text(
                prompt,
                model=self.model_name,
            )

            if not raw_text:
                raise ValueError("Empty response from LLM")
            
            # Split suggested prompts
            text_without_prompts, suggested_prompts = split_answer_and_suggested_prompts(raw_text, include_suggested_prompts)
            # Split quiz
            answer_text, quiz_data = split_answer_and_quiz(text_without_prompts, include_quiz)
            
            # Validate citations
            answer_text = parse_citations(answer_text, valid_source_ids)
            
            result = {
                "answer": answer_text,
                "sources": web_sources,
                "truncated": False,
                "quiz": quiz_data,
                "suggested_prompts": suggested_prompts,
            }
            self._cache_result(cache_key, result)
            return result
            
        except asyncio.TimeoutError:
            result = {"answer": "Web search timed out.", "sources": [], "truncated": True, "timed_out": True}
            self._cache_result(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return {"answer": "Web search is currently unavailable. Please try again or check that the Tavily API key is configured.", "sources": [], "truncated": True, "error": str(e)}
            
    async def search_with_kb_context(self, query: str, kb_context: str, kb_sources: List[str], timeout_ms: int | None = None) -> Dict[str, Any]:
        """Perform web search with knowledge base context for hybrid answers."""
        sanitized_query = sanitize_query(query)
        sanitized_kb_context = sanitize_kb_context(kb_context)
        kb_fallback_snippet = sanitized_kb_context[:1000] if sanitized_kb_context else ""

        try:
            # Fetch search results
            search_results = await self.search_provider.search(sanitized_query, max_results=5)
            
            web_sources = []
            valid_source_ids = []
            search_results_text = "<search_results>\n"
            for res in search_results:
                search_results_text += f"[{res.id}]\nTitle: {res.title}\nURL: {res.url}\nContent: {res.content}\n\n"
                web_sources.append({"title": res.title, "url": res.url, "snippet": res.content, "type": "web_search", "id": res.id})
                valid_source_ids.append(res.id)
            search_results_text += "</search_results>"
            
            include_quiz = should_generate_quiz(sanitized_query)
            quiz_instruction = build_quiz_instruction(include_quiz)
            include_suggested_prompts = should_generate_suggested_prompts(sanitized_query)
            suggested_prompts_instruction = build_suggested_prompts_instruction(include_suggested_prompts)
            
            prompt = f"""<system_role>
You are an expert VCM assistant with access to web search results.
</system_role>

<instructions>
1. Synthesis: Answer directly and authoritatively. Seamlessly merge the <reference_data> information with your web search results.
2. No Preambles: NEVER use introductory phrases.
3. Silent Sourcing:
   - Cite web sources using the [Web, cite: N] format where N is the source number from the search results (e.g., [Web, cite: 1]).
   - Cite knowledge base sources using the [cite_kb: N] format where N is the source index from the <reference_data> <source index="N"> tags.
   - Do NOT invent new sources and do NOT combine KB and web citations into a single bracket.
4. Formatting & Word Limits:
   - Simple questions: Maximum 150 words.
   - Detailed questions: MAXIMUM 600 words using markdown.
5. {quiz_instruction}
6. {suggested_prompts_instruction}
</instructions>

{search_results_text}

<reference_data>
{sanitized_kb_context}
</reference_data>

<user_query>
{sanitized_query}
</user_query>"""

            raw_text = await self.llm.generate_text(
                prompt,
                model=self.model_name,
            )
            text_without_prompts, suggested_prompts = split_answer_and_suggested_prompts(raw_text, include_suggested_prompts)
            answer_text, quiz_data = split_answer_and_quiz(text_without_prompts, include_quiz)
            
            answer_text = parse_citations(answer_text, valid_source_ids)
            
            combined_sources = _kb_sources_to_dicts(kb_sources) + web_sources
            
            return {
                "answer": answer_text,
                "sources": combined_sources,
                "kb_sources": kb_sources,
                "web_sources": web_sources,
                "hybrid": True,
                "truncated": False,
                "quiz": quiz_data,
                "suggested_prompts": suggested_prompts,
            }
        except asyncio.TimeoutError:
            return {
                "answer": kb_fallback_snippet,
                "sources": _kb_sources_to_dicts(kb_sources),
                "kb_sources": kb_sources,
                "web_sources": [],
                "hybrid": False,
                "truncated": True,
                "timed_out": True,
            }
        except Exception as e:
            logger.error(f"Web search with KB context failed: {e}")
            return {
                "answer": kb_fallback_snippet,
                "sources": _kb_sources_to_dicts(kb_sources),
                "kb_sources": kb_sources,
                "web_sources": [],
                "hybrid": False,
                "truncated": True,
                "error": str(e),
            }