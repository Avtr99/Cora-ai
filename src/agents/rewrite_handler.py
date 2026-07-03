"""
Query Rewrite Handler

Handles query rewriting with two-tier caching:
- L1: In-memory TTLCache (fast, ephemeral, catches rapid-fire duplicates)
- L2: SQLite (persistent, survives application restarts)
"""

import datetime
import hashlib
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from cachetools import TTLCache

from .reasoning_formatter import AgentStep
from .orchestrator_query_utils import (
    DEFAULT_FULL_REWRITE_QUERY_TYPES,
    DEFAULT_TIME_SENSITIVE_MARKERS,
    attach_current_date_context,
    cache_key,
    select_rewrite_mode,
)
from ..db.sqlite_cache import SQLiteCache

logger = logging.getLogger(__name__)


class RewriteHandler:
    """Handles query rewriting with two-tier caching (L1 in-memory + L2 SQLite)."""
    
    _HANDLER_TYPE = "rewrite"
    
    def __init__(
        self,
        query_rewriter: Any,
        use_quick_rewrite: bool = False,
        cache_ttl: int = 600,
        cache_maxsize: int = 500,
        sqlite_cache: Optional[SQLiteCache] = None,
        l2_ttl_seconds: int = 86400,
    ):
        """
        Initialize the rewrite handler.
        
        Args:
            query_rewriter: QueryRewriterAgent instance
            use_quick_rewrite: If True, prefer quick local expansion
            cache_ttl: L1 cache TTL in seconds (default 10 min)
            cache_maxsize: Maximum L1 cache size
            sqlite_cache: Optional L2 persistent cache
            l2_ttl_seconds: L2 cache TTL in seconds (default 24h)
        """
        self.query_rewriter = query_rewriter
        self.use_quick_rewrite = use_quick_rewrite
        self._cache = TTLCache(maxsize=cache_maxsize, ttl=cache_ttl)
        self._l2_cache = sqlite_cache
        self._l2_ttl = l2_ttl_seconds
    
    async def rewrite(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]],
        steps: List[AgentStep],
        enable_rewriting: bool = True,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Rewrite the query for better retrieval.
        
        Args:
            query: Original query string
            chat_history: Optional conversation history
            steps: List to append AgentStep to
            enable_rewriting: Whether rewriting is enabled
            
        Returns:
            Tuple of (rewritten_query, rewrite_info_dict)
        """
        step_start = time.time()
        
        if not enable_rewriting:
            steps.append(AgentStep(
                name="Query Rewriting",
                status="skipped",
                details={"reason": "Disabled in config"}
            ))
            return query, {}
        
        rewrite_mode, query_type = select_rewrite_mode(
            query,
            chat_history,
            use_quick_rewrite=self.use_quick_rewrite,
            full_rewrite_types=DEFAULT_FULL_REWRITE_QUERY_TYPES,
        )

        # Check L1 cache first (cost optimization)
        rewrite_cache_key = cache_key(f"rewrite:{rewrite_mode}", query, chat_history)
        if rewrite_cache_key in self._cache:
            cached_result = self._handle_cache_hit(
                rewrite_cache_key, query, rewrite_mode, query_type, step_start, steps
            )
            if cached_result is not None:
                return cached_result

        # Check L2 (SQLite) cache
        if self._l2_cache and self._l2_cache.enabled:
            l2_data = await self._l2_cache.get(rewrite_cache_key, self._HANDLER_TYPE)
            if l2_data is not None:
                # Populate L1 from L2 hit
                self._cache[rewrite_cache_key] = l2_data
                logger.debug("L2 cache hit for %s key: %s", self._HANDLER_TYPE, rewrite_cache_key[:16])
                cached_result = self._handle_cache_hit(
                    rewrite_cache_key, query, rewrite_mode, query_type, step_start, steps
                )
                if cached_result is not None:
                    return cached_result

        if rewrite_mode == "quick_expand":
            return await self._quick_expand(
                query, query_type, rewrite_cache_key, step_start, steps
            )
        
        # Full LLM rewrite
        return await self._llm_rewrite(
            query, chat_history, query_type, rewrite_cache_key, step_start, steps
        )
    
    def _handle_cache_hit(
        self,
        rewrite_cache_key: str,
        query: str,
        rewrite_mode: str,
        query_type: str,
        step_start: float,
        steps: List[AgentStep],
    ) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Handle cache hit for rewrite."""
        cached = self._cache.get(rewrite_cache_key)
        if cached is None:
            return None
        duration = (time.time() - step_start) * 1000
        steps.append(AgentStep(
            name="Query Rewriting",
            status="cached",
            duration_ms=round(duration, 2),
            details={
                "cached": True,
                "rewritten": cached["rewritten_query"],
                "method": cached.get("method", rewrite_mode),
                "query_type": cached.get("query_type", query_type),
            }
        ))
        if logger.isEnabledFor(logging.DEBUG):
            query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
            logger.debug("Rewrite cache hit for query hash: %s", query_hash)
        return cached["rewritten_query"], cached
    
    async def _quick_expand(
        self,
        query: str,
        query_type: str,
        rewrite_cache_key: str,
        step_start: float,
        steps: List[AgentStep],
    ) -> Tuple[str, Dict[str, Any]]:
        """Perform quick local acronym expansion."""
        current_date = datetime.date.today().isoformat()
        rewritten = self.query_rewriter.quick_expand_acronyms(query)
        rewritten = attach_current_date_context(
            rewritten,
            current_date,
            markers=DEFAULT_TIME_SENSITIVE_MARKERS,
        )
        duration = (time.time() - step_start) * 1000
        
        result = {
            "rewritten_query": rewritten,
            "method": "quick_expand",
            "query_type": query_type,
            "current_date": current_date,
            "detected_intent": query_type,
            "corrections_made": [],
        }
        
        steps.append(AgentStep(
            name="Query Rewriting",
            status="completed",
            duration_ms=round(duration, 2),
            details={
                "method": "quick_expand",
                "query_type": query_type,
                "current_date": current_date,
                "original": query,
                "rewritten": rewritten,
                "intent": query_type,
            }
        ))
        
        # Cache result in L2 (persistent) then L1 (in-memory)
        if self._l2_cache and self._l2_cache.enabled:
            try:
                await self._l2_cache.set(
                    rewrite_cache_key, self._HANDLER_TYPE, result, ttl_seconds=self._l2_ttl
                )
            except Exception as l2_exc:
                logger.warning(
                    "L2 cache write failed for %s key %s: %s. Continuing with L1 cache.",
                    self._HANDLER_TYPE,
                    rewrite_cache_key[:16],
                    l2_exc,
                )
        self._cache[rewrite_cache_key] = result
        return rewritten, result
    
    async def _llm_rewrite(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]],
        query_type: str,
        rewrite_cache_key: str,
        step_start: float,
        steps: List[AgentStep],
    ) -> Tuple[str, Dict[str, Any]]:
        """Perform full LLM-based rewrite."""
        current_date = datetime.date.today().isoformat()
        
        try:
            result = await self.query_rewriter.rewrite(query, chat_history)
            rewritten = attach_current_date_context(
                result.get("rewritten_query", query),
                current_date,
                markers=DEFAULT_TIME_SENSITIVE_MARKERS,
            )
            status = "completed"
            error_msg = None
        except Exception as e:
            logger.error("LLM rewrite failed: %s", e, exc_info=True)
            rewritten = attach_current_date_context(
                query,
                current_date,
                markers=DEFAULT_TIME_SENSITIVE_MARKERS,
            )
            result = {
                "rewritten_query": rewritten,
                "corrections_made": [],
                "detected_intent": query_type,
                "error": "rewrite failed due to internal error",
            }
            status = "failed"
            error_msg = "rewrite failed due to internal error"
        
        duration = (time.time() - step_start) * 1000
        
        steps.append(AgentStep(
            name="Query Rewriting",
            status=status,
            duration_ms=round(duration, 2),
            details={
                "method": "llm",
                "query_type": query_type,
                "current_date": current_date,
                "original": query,
                "rewritten": rewritten,
                "corrections": result.get("corrections_made", []),
                "intent": result.get("detected_intent", query_type),
                **({"error": error_msg} if error_msg else {})
            }
        ))

        result["query_type"] = query_type
        result["current_date"] = current_date
        result["method"] = "llm"

        # Cache result only for successful rewrites
        if not result.get("error"):
            if self._l2_cache and self._l2_cache.enabled:
                try:
                    await self._l2_cache.set(
                        rewrite_cache_key, self._HANDLER_TYPE, result, ttl_seconds=self._l2_ttl
                    )
                except Exception as l2_exc:
                    logger.warning(
                        "L2 cache write failed for %s key %s: %s. Continuing with L1 cache.",
                        self._HANDLER_TYPE,
                        rewrite_cache_key[:16],
                        l2_exc,
                    )
            self._cache[rewrite_cache_key] = result
        return rewritten, result
