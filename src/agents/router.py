"""
Query Router Agent

Decides whether a user query should be answered from the local knowledge base,
web search, or a hybrid of both. A fast heuristic pass handles clear VCM/web
signals; ambiguous queries (no keyword match) fall back to the configured lite
LLM for domain-agnostic routing.
"""

import json
import logging
import re
from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum

from ..registry_config.registry_patterns import REGISTRY_PATTERNS, RegistryPattern
from ..config import get_settings

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Registry-pattern helpers
# ------------------------------------------------------------------

def _load_custom_registry_patterns(path: Optional[str]) -> List[RegistryPattern]:
    """Load extra registry patterns from a JSON file.

    The JSON file should contain a list of objects with the same fields as
    RegistryPattern: name, content_markers, id_patterns, version_patterns.
    """
    if not path:
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            logger.warning("CUSTOM_REGISTRY_PATTERNS file must contain a JSON list")
            return []
        patterns = []
        for item in data:
            if not isinstance(item, dict):
                continue
            patterns.append(
                RegistryPattern(
                    name=item.get("name", "Custom"),
                    content_markers=item.get("content_markers", []) or [],
                    id_patterns=item.get("id_patterns", []) or [],
                    version_patterns=item.get("version_patterns", []) or [],
                )
            )
        logger.info("Loaded %d custom registry patterns from %s", len(patterns), path)
        return patterns
    except FileNotFoundError:
        logger.warning("CUSTOM_REGISTRY_PATTERNS file not found: %s", path)
        return []
    except Exception as e:
        logger.warning("Failed to load CUSTOM_REGISTRY_PATTERNS: %s", e)
        return []


def _merge_registry_patterns() -> List[RegistryPattern]:
    """Return built-in VCM patterns merged with optional custom patterns."""
    merged = list(REGISTRY_PATTERNS)
    try:
        custom_path = get_settings().CUSTOM_REGISTRY_PATTERNS
    except Exception:
        custom_path = None
    custom = _load_custom_registry_patterns(custom_path)
    if custom:
        merged = merged + custom
    return merged


def _build_kb_keywords(patterns: List[RegistryPattern]) -> set[str]:
    """Build KB keywords from the given registry patterns.

    Args:
        patterns: Registry patterns to extract content markers from.

    Returns:
        Set of lower-case keyword strings.
    """
    keywords = set()
    for pattern in patterns:
        for marker in pattern.content_markers:
            keywords.add(marker.lower())
    return keywords


def _build_doc_id_patterns(patterns: List[RegistryPattern]) -> list[str]:
    """Build document ID regex patterns from the given registry patterns.

    Args:
        patterns: Registry patterns to extract id patterns from.

    Returns:
        List of regex pattern strings.
    """
    patterns_out = []
    for rp in patterns:
        for p in rp.id_patterns:
            if p not in patterns_out:
                patterns_out.append(p)
    return patterns_out


# ------------------------------------------------------------------
# Temporal cutoff
# ------------------------------------------------------------------

def _kb_market_data_cutoff_year() -> int:
    """Return the year beyond which market/pricing queries should use web search.

    Defaults to the previous year so the cutoff ages automatically without
    manual code changes. Can be pinned to a fixed year via settings.
    """
    try:
        settings = get_settings()
        if settings.KB_MARKET_DATA_CUTOFF_YEAR is not None:
            return settings.KB_MARKET_DATA_CUTOFF_YEAR
    except Exception:
        pass
    return datetime.now().year - 1


# ------------------------------------------------------------------
# Router prompt (built lazily per RouterAgent instance so it picks up
# current settings, including COLLECTION_DESCRIPTION, at init time)
# ------------------------------------------------------------------

def _build_router_prompt(patterns: List[RegistryPattern]) -> str:
    """Build the router prompt dynamically from merged registry patterns.

    This ensures the LLM router always knows exactly what registries
    and document categories are in the KB, without manual updates.
    """
    category_lines = []
    for p in patterns:
        # Use the first few content markers as illustrative examples
        examples = ", ".join(p.content_markers[:4])
        category_lines.append(f"- {p.name} ({examples})")
    categories_block = "\n".join(category_lines)

    cutoff_year = _kb_market_data_cutoff_year()
    next_year = cutoff_year + 1

    collection_description = ""
    try:
        settings = get_settings()
        if settings.COLLECTION_DESCRIPTION:
            collection_description = f"\nAdditional knowledge base contents:\n{settings.COLLECTION_DESCRIPTION}\n"
    except Exception:
        pass

    return f"""You are a query router for a knowledge base.

The knowledge base is primarily focused on Voluntary Carbon Market (VCM) documents: registries, methodologies, standards, policies, and market intelligence.

The knowledge base contains documents about the following registries and topics:
{categories_block}
{collection_description}
IMPORTANT RULES:
- The KB has market/pricing data up to mid-{cutoff_year}. For data after that, use web_search.
- If the query mentions a year >= {next_year} together with market data, prices, or forecasts, route to web_search.
- If the user asks "latest" or "current" about prices/market, route to web_search.
- If the query is clearly about VCM concepts, methodologies, policies, or standards with no time-sensitivity, route to knowledge_base.
- If the query is about the additional knowledge base contents described above, route to knowledge_base.
- If unsure and the query has VCM context, route to knowledge_base (let the system fall back if needed).

Decide the best route for the query:
1. "knowledge_base" - Query is about topics covered by the KB
2. "web_search" - Query needs real-time info, post-{cutoff_year} data, news, or is outside KB scope
3. "hybrid" - Try knowledge base first, use web if insufficient

Return ONLY a JSON object:
{{
    "route": "knowledge_base" | "web_search" | "hybrid",
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}

Query: """


# --- Pre-computed sets for zero-cost lookups at request time ---

# Time-sensitive / recency markers that suggest web search
_WEB_KEYWORDS: set[str] = {
    "latest", "recent", "news", "today", "current price",
    "stock", "weather", "who is", "what happened",
    "2026", "2027",  # KB only covers up to mid-2025
}

# Year pattern for market-intelligence time-check
_YEAR_RE = re.compile(r'\b(20[2-9]\d)\b')

# Market context words — used only in combination with year checks
_MARKET_WORDS: set[str] = {
    "price", "prices", "forecast", "market report", "market trends",
    "state of the market", "carbon pricing", "credit price",
}

# Broad domain terms are useful routing signals but too common for document
# category classification. Keep them separate from RegistryPattern markers.
_ROUTING_ONLY_KB_KEYWORDS: frozenset[str] = frozenset(
    {"carbon market", "voluntary carbon market"}
)


class RouteDecision(Enum):
    """Possible routing decisions."""
    KNOWLEDGE_BASE = "knowledge_base"
    WEB_SEARCH = "web_search"
    HYBRID = "hybrid"


class RouterAgent:
    """
    Agent that routes queries to the appropriate data source.

    Two-pass routing:
    1. **Heuristic pass** (zero-cost): keyword counting, document-ID regex,
       year/market checks. Handles clear VCM and real-time queries without
       an LLM call.
    2. **LLM fallback** (lite model): for ambiguous queries where no heuristic
       signal matched. The LLM is domain-agnostic — it can infer that
       "scope 3 emissions accounting" belongs in the KB even without a VCM
       keyword match, which the heuristic cannot.

    Keywords and document ID patterns are dynamically derived from
    REGISTRY_PATTERNS in metadata_extractor.py so the router always
    stays in sync with what the KB actually contains.
    """

    def __init__(self, llm_client, model_name: Optional[str] = None):
        """
        Initialize the router agent.

        Args:
            llm_client: LLMClient instance used for the ambiguous-query fallback.
            model_name: Model to use for routing. When None, the client's lite
                model is used for low latency.
        """
        self.llm = llm_client
        self.model_name = model_name

        # Built-in VCM patterns merged with optional custom patterns. Custom
        # patterns are loaded once at router initialization time.
        self._registry_patterns: List[RegistryPattern] = _merge_registry_patterns()
        self.kb_keywords: set[str] = (
            _build_kb_keywords(self._registry_patterns) | _ROUTING_ONLY_KB_KEYWORDS
        )
        self.doc_id_patterns: list[str] = _build_doc_id_patterns(self._registry_patterns)
        self.kb_category_names: set[str] = {p.name.lower() for p in self._registry_patterns}

        # Build the LLM router prompt once at init so it picks up the current
        # COLLECTION_DESCRIPTION and registry patterns without a module-load
        # race with settings initialization.
        self._router_prompt: str = _build_router_prompt(self._registry_patterns)

        # Web search keywords (static — these are domain-independent)
        self.web_keywords: set[str] = _WEB_KEYWORDS

        logger.info(
            "Router initialized: %d KB keywords, %d doc-ID patterns from %d categories",
            len(self.kb_keywords),
            len(self.doc_id_patterns),
            len(self._registry_patterns),
        )

    async def route(self, query: str, chat_history: Optional[List[Dict]] = None) -> tuple:
        """
        Route a query to the best data source.

        Returns a tuple of (RouteDecision, confidence, reasoning).
        """
        if not query or not query.strip():
            return (RouteDecision.KNOWLEDGE_BASE, 0.5, "Empty query")

        # 1. Fast heuristic pass — handles clear VCM/web queries without an LLM call.
        quick_result = self._quick_route(query)
        if quick_result is not None:
            return quick_result

        # 2. LLM fallback for ambiguous queries (no heuristic signal matched).
        # The LLM is domain-agnostic: it can route non-VCM queries that the
        # keyword-based heuristic cannot understand.
        return await self._llm_route(query)

    def _quick_route(self, query: str) -> Optional[tuple]:
        """
        Fast rule-based routing using keywords and document IDs.

        Returns None if ambiguous (needs LLM fallback).
        """
        query_lower = query.lower()

        # --- Pass 1: Document ID detection (highest confidence) ---
        for pattern in self.doc_id_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return (RouteDecision.KNOWLEDGE_BASE, 0.95, "Document ID detected")

        # --- Pass 2: Time-sensitive market check ---
        # If query mentions a year beyond the KB cutoff AND market context, prefer web
        cutoff_year = _kb_market_data_cutoff_year()
        year_match = _YEAR_RE.search(query)
        if year_match:
            year = int(year_match.group(1))
            has_market_context = any(mw in query_lower for mw in _MARKET_WORDS)
            if year > cutoff_year and has_market_context:
                return (RouteDecision.WEB_SEARCH, 0.9, f"Market data for {year} — beyond KB coverage")

        # --- Pass 3: Keyword counting ---
        web_matches = sum(1 for kw in self.web_keywords if kw in query_lower)

        # Check for strong category name match (e.g. "verra", "gold standard", "sbti")
        category_match = any(name in query_lower for name in self.kb_category_names)

        # Count general KB keyword matches
        kb_matches = sum(1 for kw in self.kb_keywords if kw in query_lower)

        # Strong KB signal: category name match OR 2+ keyword hits, no web signals
        if (category_match or kb_matches >= 2) and web_matches == 0:
            return (RouteDecision.KNOWLEDGE_BASE, 0.9, f"Strong KB signal: {kb_matches} keyword matches")

        # Strong web signal: web keywords present, no KB context at all
        if web_matches >= 1 and kb_matches == 0:
            return (RouteDecision.WEB_SEARCH, 0.85, "Web search keywords detected, no VCM context")

        # Mixed signals: KB + web keywords both present
        # Prefer HYBRID so KB gets tried first (saves web quota)
        if kb_matches >= 1 and web_matches >= 1:
            return (RouteDecision.HYBRID, 0.7, "Mixed KB and web signals — trying KB first")

        # Single KB keyword, no web keywords — weak KB signal
        # Route to KB to save web quota; orchestrator can supplement if needed
        if kb_matches == 1 and web_matches == 0:
            return (RouteDecision.KNOWLEDGE_BASE, 0.7, "Weak KB signal (1 keyword) — trying KB first")

        # No heuristic signal matched — ambiguous. Fall back to the LLM router
        # (lite model) for domain-agnostic routing. The LLM can infer that a
        # non-VCM query like "scope 3 emissions accounting" belongs in the KB
        # even without a keyword match, which the heuristic cannot.
        return None

    async def _llm_route(self, query: str) -> tuple:
        """
        Use the lite LLM for ambiguous queries the heuristic could not classify.

        Returns a tuple of (RouteDecision, confidence, reasoning).
        """
        try:
            prompt = self._router_prompt + query

            # Use the explicitly configured model, or the client's lite model
            # for low latency. Passing model=None would resolve to the client's
            # *main* model (not lite), so we resolve the lite model explicitly.
            resolved_model = self.model_name
            if resolved_model is None and self.llm is not None:
                resolved_model = getattr(self.llm, "model_lite", None)

            result_text = await self.llm.generate_text(
                prompt,
                model=resolved_model,
                temperature=0.0,
                json_mode=True,
            )
            return self._parse_response(result_text)
        except Exception as e:
            logger.warning("LLM routing failed: %s. Defaulting to knowledge_base.", e)
            # KB-first fallback: the KB route has its own zero-result → web
            # fallback, so this is cheaper than hybrid (which always calls
            # Tavily) while still reaching web search when the KB has nothing.
            return (RouteDecision.KNOWLEDGE_BASE, 0.5, "LLM routing failed; defaulting to KB-first")

    def _parse_response(self, response_text: str) -> tuple:
        """
        Parse the JSON response from the model.

        Args:
            response_text: Raw text response from LLM

        Returns:
            Tuple of (RouteDecision, confidence, reasoning)
        """
        # Extract JSON from possible markdown code block
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if not json_match:
            logger.warning("Router returned no JSON. Response: %s", response_text[:200])
            return (RouteDecision.KNOWLEDGE_BASE, 0.5, "No JSON in router response; defaulting to KB-first")

        try:
            data = json.loads(json_match.group(0))
            route = data.get("route", "knowledge_base").lower()
            confidence = float(data.get("confidence", 0.7))
            reasoning = data.get("reasoning", "No reasoning provided")

            if route not in [decision.value for decision in RouteDecision]:
                logger.warning("Invalid route '%s'; defaulting to knowledge_base", route)
                return (RouteDecision.KNOWLEDGE_BASE, confidence, f"Invalid route: {reasoning}")

            return (RouteDecision(route), confidence, reasoning)
        except Exception as e:
            logger.warning("Failed to parse router response: %s. Response: %s", e, response_text[:200])
            return (RouteDecision.KNOWLEDGE_BASE, 0.5, "Failed to parse router response; defaulting to KB-first")
