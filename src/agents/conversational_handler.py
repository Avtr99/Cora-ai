"""
Conversational Handler

Handles conversational/meta queries with a lightweight LLM call,
bypassing the full RAG pipeline for greetings and simple chat.

Optimization: Saves 2-4 LLM calls (~2-4 seconds) for conversational queries.
"""

import asyncio
import logging
import re
import threading
import time
from typing import Any, Dict, List, Optional

from cachetools import LRUCache

from .reasoning_formatter import AgentStep
from ..citations import CitationManager
from ..config import get_settings

logger = logging.getLogger(__name__)

# Patterns for sanitizing user input to prevent prompt injection
_SUSPICIOUS_PREFIXES = re.compile(r'^(System:|Assistant:|Instructions:|>>>|\s*`)', re.IGNORECASE)
_FENCED_CODE = re.compile(r'```', re.IGNORECASE)
_CONTROL_CHARS = re.compile(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]')
_REPEATED_NEWLINES = re.compile(r'\n{3,}')

# Sentinel values for lazy initialization
_INTENT_CACHE: Optional[LRUCache[str, bool]] = None
_INTENT_CACHE_LOCK: Optional[asyncio.Lock] = None
_INIT_LOCK = threading.Lock()


def _get_intent_cache() -> LRUCache[str, bool]:
    """Lazily initialize and return the intent classification cache."""
    global _INTENT_CACHE
    if _INTENT_CACHE is None:
        with _INIT_LOCK:
            if _INTENT_CACHE is None:
                settings = get_settings()
                _INTENT_CACHE = LRUCache(maxsize=settings.CONVERSATIONAL_INTENT_CACHE_SIZE)
    return _INTENT_CACHE


def _get_intent_cache_lock() -> asyncio.Lock:
    """Lazily initialize and return the intent cache lock."""
    global _INTENT_CACHE_LOCK
    if _INTENT_CACHE_LOCK is None:
        with _INIT_LOCK:
            if _INTENT_CACHE_LOCK is None:
                _INTENT_CACHE_LOCK = asyncio.Lock()
    return _INTENT_CACHE_LOCK


_INTENT_SYSTEM_PROMPT = (
    "Classify the user message as either:\n"
    "- conversational (greeting, thanks, chitchat, self-introduction)\n"
    "- domain_query (asking about carbon markets, VCS, emissions, methodologies, climate policy, etc.)\n\n"
    "Respond with exactly one word: conversational or domain_query."
)


def _sanitize_input(text: str, max_length: int = 2000) -> str:
    """Sanitize user input to prevent prompt injection.

    - Trims to max_length
    - Strips control characters
    - Removes/replaces suspicious role prefixes
    - Collapses repeated newlines
    - Neutralizes fenced code markers

    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length (default 2000 for safety)

    Returns:
        Sanitized text safe for prompt inclusion
    """
    if not text:
        return ""

    # Trim length first to avoid processing huge inputs
    if len(text) > max_length:
        text = text[:max_length]

    # Remove control characters
    text = _CONTROL_CHARS.sub('', text)

    # Collapse repeated newlines
    text = _REPEATED_NEWLINES.sub('\n\n', text)

    # Neutralize fenced code markers by breaking them
    text = _FENCED_CODE.sub('` ``', text)

    # Remove or neutralize suspicious role-like prefixes
    # This prevents users from injecting system/assistant/instructions
    lines = text.split('\n')
    sanitized_lines = []
    for line in lines:
        stripped = line.lstrip()
        if _SUSPICIOUS_PREFIXES.match(stripped):
            # Neutralize by escaping the prefix
            line = '[User] ' + line.lstrip()
        sanitized_lines.append(line)

    return '\n'.join(sanitized_lines)


# System instruction for conversational responses (no RAG context needed)
CONVERSATIONAL_SYSTEM_INSTRUCTION = """You are Cora, a helpful AI assistant specializing in carbon markets and sustainability.

Your task: Determine if this is a simple greeting/conversational message OR a request for information.

For greetings/conversational messages (respond normally):
- "hi", "hello", "thanks", "how are you", etc.
- Respond warmly and professionally
- Keep responses concise (1-2 sentences)
- Offer to help with carbon market questions if appropriate

For information requests (respond with "ROUTE_TO_RAG"):
- User asks about specific entities (e.g., "tell me about VM0048")
- User asks questions requiring document lookup
- User asks for facts, data, or explanations
- ANY query that requires knowledge from documents

You do NOT have access to documents for this response. If the user is asking for information, respond with exactly "ROUTE_TO_RAG" to pass to the full RAG pipeline."""


class ConversationalHandler:
    """
    Handles conversational queries with a single lightweight LLM call.
    
    Skips: rewriting, routing, retrieval, citation extraction.
    Cost: 1 LLM call (vs 3-4 in full pipeline).
    """
    
    def __init__(self, llm_client, model_name: Optional[str] = None):
        """
        Initialize the conversational handler.

        Args:
            llm_client: LLMClient instance used for text generation
            model_name: Model to use (defaults to lite model for speed)
        """
        self.llm = llm_client
        settings = get_settings()
        # Use lite model for conversational responses (faster, cheaper)
        self.model_name = model_name or getattr(
            settings, "GEMINI_MODEL_LITE", "gemini-2.5-flash-lite"
        )
    
    @staticmethod
    def is_conversational(query: str, chat_history: Optional[List[Dict[str, str]]] = None) -> bool:
        """
        Check if query is conversational/greeting that doesn't need RAG.
        
        Args:
            query: User query string
            chat_history: Optional conversation history
            
        Returns:
            True if query is conversational AND no meaningful history exists.
            If history exists, we must pass to RAG to allow context-aware answers.
        """
        if chat_history and len(chat_history) > 0:
            # We have history, so this might be a context-dependent query
            # (e.g., "what is my favorite color?"). Pass to full RAG.
            return False
            
        return CitationManager.is_conversational_query(query)

    async def should_handle(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> bool:
        """Return True when the conversational handler should bypass RAG.

        Strategy (preserved from the original implementation):
        - If chat history exists, NEVER bypass — the query may be a
          context-dependent follow-up (e.g. "what is my favorite color?"),
          so it must go to the full RAG pipeline for context-aware answering.
          Both ``is_conversational`` and ``classify_intent`` short-circuit to
          False when history is present.
        - Otherwise, the cheap regex heuristic (``is_conversational``) runs
          first — no extra latency/cost.
        - If the heuristic is not confident, a tiny LLM intent check
          (``classify_intent``, gemini-flash-lite) classifies short ambiguous
          queries, with decisions cached per normalized query.

        Callers that gate a query cache lookup should call ``is_conversational``
        directly before the cache check and defer ``classify_intent`` until
        after a cache miss, so cached starter prompts are served with zero LLM
        cost. See ``RAGOrchestrator._try_conversational``.
        """
        if self.is_conversational(query, chat_history):
            return True
        return await self.classify_intent(query, chat_history)

    async def classify_intent(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> bool:
        """LLM intent classification for short ambiguous queries.

        Called only after the cheap heuristic (``is_conversational``) returned
        False and the query cache missed. Uses a single tiny gemini-flash-lite
        call, with decisions cached per normalized query (in-memory LRU).

        Returns False (do not bypass) when chat history exists, the query is
        long (> 12 words), or classification fails — defaulting to the full
        RAG pipeline.
        """
        if chat_history and len(chat_history) > 0:
            return False

        if not query:
            return False

        normalized = re.sub(r"\s+", " ", query.strip().lower())
        async with _get_intent_cache_lock():
            cached = _get_intent_cache().get(normalized)
            if cached is not None:
                return cached

        # Only pay for classification when the query is short enough to plausibly
        # be a greeting/acknowledgement, but wasn't caught by the heuristic.
        word_count = len(re.findall(r"\b\w+\b", normalized))
        if word_count > 12:
            async with _get_intent_cache_lock():
                _get_intent_cache()[normalized] = False
            return False

        prompt = f"{_INTENT_SYSTEM_PROMPT}\n\nUser: {_sanitize_input(query)}"

        settings = get_settings()
        try:
            intent_text = await self.llm.generate_text(
                prompt,
                model=self.model_name,
                temperature=0.0,
                top_p=1.0,
                max_output_tokens=settings.CONVERSATIONAL_INTENT_MAX_TOKENS,
            )
            label = (intent_text or "").strip().lower()
            decision = label == "conversational"
        except Exception as exc:
            logger.warning("Intent classification failed; defaulting to RAG: %s", exc)
            decision = False

        async with _get_intent_cache_lock():
            _get_intent_cache()[normalized] = decision
        return decision
    
    async def handle(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        steps: Optional[List[AgentStep]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Handle a conversational query with a single lightweight LLM call.
        
        Args:
            query: User's conversational query
            chat_history: Optional conversation history for context
            steps: Optional list to append AgentStep to
            
        Returns:
            Response dict with answer and metadata
        """
        step_start = time.time()
        steps = steps if steps is not None else []

        # Build prompt with optional chat history context
        prompt = self._build_prompt(query, chat_history)
        settings = get_settings()
        
        try:
            answer = await self.llm.generate_text(
                prompt,
                model=self.model_name,
                temperature=0.7,
                top_p=0.9,
                max_output_tokens=settings.CONVERSATIONAL_MAX_OUTPUT_TOKENS,
            )
            if not answer:
                answer = "Hello! How can I help you with carbon markets today?"
            
            # Check if LLM wants to route to RAG (detects information requests)
            if "ROUTE_TO_RAG" in answer:
                logger.info("Conversational handler detected RAG query, passing to full pipeline")
                return None  # Signal fallback to RAG
            
            duration_ms = round((time.time() - step_start) * 1000, 2)
            
            # Record step
            steps.append(AgentStep(
                name="Conversational Response",
                status="completed",
                duration_ms=duration_ms,
                details={
                    "type": "conversational_gate",
                    "model": self.model_name,
                    "bypassed_rag": True,
                }
            ))
            
            # Token usage not available via the unified generate_text interface
            tokens_in = 0
            tokens_out = 0
            
            return {
                "answer": answer,
                "sources": [],
                "citations": {"count": 0, "sources": [], "details": []},
                "coverage_score": 0.0,
                "meta": {
                    "model": self.model_name,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "conversational_gate": True,
                },
            }
            
        except Exception as e:
            logger.warning("Conversational handler failed, will fall through to RAG: %s", e)
            # Return None to signal fallback to full RAG pipeline
            return None
    
    def _build_prompt(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        Build prompt for conversational response.
        
        Includes chat history for context-aware responses (e.g., "Thanks" knows
        what the user is thanking for).
        
        Args:
            query: User's query
            chat_history: Optional conversation history
            
        Returns:
            Full prompt string
        """
        parts = [CONVERSATIONAL_SYSTEM_INSTRUCTION]
        
        # Include recent chat history for context
        if chat_history:
            parts.append("\n--- Recent Conversation ---")
            # Include last 3 exchanges for context
            recent = chat_history[-6:] if len(chat_history) > 6 else chat_history
            for msg in recent:
                role = msg.get("role", "user").capitalize()
                content = _sanitize_input(msg.get("content", "")[:500])  # Truncate and sanitize
                parts.append(f"{role}: {content}")
            parts.append("--- End Conversation ---\n")
        
        parts.append(f"User: {_sanitize_input(query)}")
        parts.append("\nRespond naturally and concisely:")
        
        return "\n".join(parts)
