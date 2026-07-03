"""
Query Routing Handler

Handles query routing with two-tier caching:
- L1: In-memory TTLCache (fast, ephemeral, catches rapid-fire duplicates)
- L2: SQLite (persistent, survives application restarts)
"""

import asyncio
import hashlib
import logging
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, Protocol, Tuple, runtime_checkable

from cachetools import TTLCache

from .reasoning_formatter import AgentStep
from .router import RouteDecision
from .orchestrator_query_utils import cache_key
from ..db.sqlite_cache import SQLiteCache

logger = logging.getLogger(__name__)


@runtime_checkable
class RouterProtocol(Protocol):
    """Protocol for router implementations."""
    
    async def route(self, query: str) -> Tuple[RouteDecision, float, str]:
        """Route query and return (decision, confidence, reason)."""
        ...


class RoutingHandler:
    """Handles query routing with two-tier caching (L1 in-memory + L2 SQLite)."""
    
    def __init__(
        self,
        router: RouterProtocol,
        default_route: RouteDecision = RouteDecision.KNOWLEDGE_BASE,
        cache_ttl: int = 600,
        cache_maxsize: int = 500,
        sqlite_cache: Optional[SQLiteCache] = None,
        l2_ttl_seconds: int = 86400,
    ):
        """
        Initialize the routing handler.
        
        Args:
            router: Router implementing route() method
            default_route: Default route when routing is disabled
            cache_ttl: L1 cache TTL in seconds (default 10 min)
            cache_maxsize: Maximum L1 cache size
            sqlite_cache: Optional L2 persistent cache
            l2_ttl_seconds: L2 cache TTL in seconds (default 24h)
        """
        self.router = router
        self.default_route = default_route
        self._cache = TTLCache(maxsize=cache_maxsize, ttl=cache_ttl)
        self._inflight: Dict[str, asyncio.Future[Dict[str, Any]]] = {}
        self._l2_cache = sqlite_cache
        self._l2_ttl = l2_ttl_seconds
        self._handler_type = "route"
    
    async def _run_with_dedup(
        self,
        cache_key: str,
        compute_fn: Callable[..., Awaitable[Any]],
        on_cache_hit: Optional[Callable] = None,
        on_complete: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Execute operation with caching and in-flight deduplication.

        Performs cache check, awaits existing future if present, creates new
        future, runs compute coroutine, handles success/failure, and always
        cleans up in-flight entry.

        Args:
            cache_key: Key for cache and deduplication lookup
            compute_fn: Callable that returns the result dict
            on_cache_hit: Optional callback called on cache hit (receives cached result)
            on_complete: Optional callback called on successful completion (receives result)
            on_error: Optional callback called on error (receives exception)

        Returns:
            Result dict from compute_fn or cache

        Raises:
            Exception: Re-raises any exception from compute_fn
        """
        # Check L1 cache first
        if cache_key in self._cache:
            result = self._cache[cache_key]
            if on_cache_hit:
                on_cache_hit(result)
            return result

        # Check L2 (SQLite) cache
        if self._l2_cache and self._l2_cache.enabled:
            l2_data = await self._l2_cache.get(cache_key, self._handler_type)
            if l2_data is not None:
                # Deserialize RouteDecision enum from string
                result = self._deserialize_route_result(l2_data, cache_key)
                if result is None:
                    # Deserialization failed (e.g., unknown route value), treat as miss
                    logger.warning(
                        "L2 cache deserialization failed for %s key: %s",
                        self._handler_type,
                        cache_key[:16]
                    )
                    # Continue processing as cache miss (don't write to L1, don't return)
                else:
                    # Populate L1 from L2 hit
                    self._cache[cache_key] = result
                    if on_cache_hit:
                        on_cache_hit(result)
                    logger.debug("L2 cache hit for %s key: %s", self._handler_type, cache_key[:16])
                    return result

        # Check for in-flight request (deduplication)
        future = self._inflight.get(cache_key)
        if future is not None:
            try:
                result = await future
                return result
            except Exception:
                # If the in-flight request failed, re-check for a new future
                # that may have been inserted by another coroutine
                future = self._inflight.get(cache_key)
                if future is not None:
                    result = await future
                    return result

        # Create future for this request
        future: asyncio.Future[Dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._inflight[cache_key] = future

        try:
            result = await compute_fn()

            # Save to L2 (persistent) first - best effort, don't block on failure
            if self._l2_cache and self._l2_cache.enabled:
                try:
                    await self._l2_cache.set(
                        cache_key,
                        self._handler_type,
                        self._serialize_route_result(result),
                        ttl_seconds=self._l2_ttl,
                    )
                except Exception as l2_exc:
                    logger.warning(
                        "L2 cache write failed for %s key %s: %s. Continuing with L1 cache.",
                        self._handler_type,
                        cache_key[:16],
                        l2_exc
                    )

            # Save to L1 (in-memory)
            self._cache[cache_key] = result

            # Resolve future for waiting coroutines
            future.set_result(result)
            if on_complete:
                on_complete(result)
            return result
        except Exception as e:
            # Fail the future so waiters get the exception
            future.set_exception(e)
            if on_error:
                on_error(e)
            raise
        finally:
            # Clean up in-flight entry
            self._inflight.pop(cache_key, None)

    @staticmethod
    def _serialize_route_result(result: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize route result for JSONB storage (convert enum to string)."""
        serialized = dict(result)
        if isinstance(serialized.get("route"), RouteDecision):
            serialized["route"] = serialized["route"].value
        return serialized

    @staticmethod
    def _deserialize_route_result(data: Dict[str, Any], cache_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Deserialize route result from JSONB (convert string back to enum)."""
        deserialized = dict(data)
        route_value = deserialized.get("route")
        if isinstance(route_value, str):
            try:
                deserialized["route"] = RouteDecision(route_value)
            except ValueError:
                # Log only non-sensitive identifiers; data may contain PII
                allowed_keys = sorted([k for k in data.keys() if k != "cached_data"])
                logger.warning(
                    "Unknown route value from L2 cache: %s for cache_key=%s (allowed_keys=%s)",
                    route_value,
                    cache_key,
                    allowed_keys
                )
                return None  # Force recomputation
        return deserialized

    async def route_raw(
        self,
        query: str,
        enable_routing: bool = True,
    ) -> Tuple[RouteDecision, float, str]:
        """
        Route the query without recording a step. Used for preliminary routing.

        Args:
            query: Query string to route
            enable_routing: Whether routing is enabled

        Returns:
            Tuple of (route_decision, confidence, reason)
        """
        if not enable_routing:
            return self.default_route, 1.0, "Default route"

        route_cache_key = cache_key("route", query)

        async def compute():
            route, confidence, reason = await self.router.route(query)
            return {
                "route": route,
                "confidence": confidence,
                "reason": reason
            }

        result = await self._run_with_dedup(route_cache_key, compute)
        return result["route"], result["confidence"], result["reason"]

    async def route(
        self,
        query: str,
        steps: List[AgentStep],
        enable_routing: bool = True,
    ) -> Tuple[RouteDecision, float, str]:
        """
        Route the query to appropriate data source.

        Args:
            query: Query string to route
            steps: List to append AgentStep to
            enable_routing: Whether routing is enabled

        Returns:
            Tuple of (route_decision, confidence, reason)
        """
        step_start = time.time()

        if not enable_routing:
            steps.append(AgentStep(
                name="Query Routing",
                status="skipped",
                details={"reason": "Disabled, using default", "route": self.default_route.value}
            ))
            return self.default_route, 1.0, "Default route"

        route_cache_key = cache_key("route", query)

        # Define callback for cache hit
        def on_cache_hit(cached: Dict[str, Any]) -> None:
            duration = (time.time() - step_start) * 1000
            steps.append(AgentStep(
                name="Query Routing",
                status="cached",
                duration_ms=round(duration, 2),
                details={
                    "cached": True,
                    "route": cached["route"].value,
                    "confidence": cached["confidence"],
                    "reason": cached["reason"]
                }
            ))
            query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
            logger.debug(f"Route cache hit for query hash: {query_hash}")

        # Define callback for successful completion
        def on_complete(result: Dict[str, Any]) -> None:
            duration = (time.time() - step_start) * 1000
            steps.append(AgentStep(
                name="Query Routing",
                status="completed",
                duration_ms=round(duration, 2),
                details={
                    "route": result["route"].value,
                    "confidence": result["confidence"],
                    "reason": result["reason"]
                }
            ))

        # Define callback for error
        def on_error(e: Exception) -> None:
            duration = (time.time() - step_start) * 1000
            query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
            logger.exception("Routing failed for query hash: %s", query_hash)
            steps.append(AgentStep(
                name="Query Routing",
                status="failed",
                duration_ms=round(duration, 2),
                details={
                    "route": None,
                    "confidence": 0.0,
                    "reason": "Routing failed"
                }
            ))

        # Define compute function
        async def compute() -> Dict[str, Any]:
            route, confidence, reason = await self.router.route(query)
            return {
                "route": route,
                "confidence": confidence,
                "reason": reason
            }

        result = await self._run_with_dedup(
            route_cache_key,
            compute,
            on_cache_hit=on_cache_hit,
            on_complete=on_complete,
            on_error=on_error
        )

        return result["route"], result["confidence"], result["reason"]
