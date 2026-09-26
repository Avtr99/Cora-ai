"""
Comprehensive health check endpoints for monitoring system components.
Checks Qdrant, external API connectivity, and cache status.
"""
import time
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from enum import Enum
from cachetools import TTLCache
from loguru import logger

from ..config import get_settings
from ..version import __version__


HEALTH_CACHE_TTL_SECONDS = 15

_health_cache: TTLCache = TTLCache(maxsize=1, ttl=HEALTH_CACHE_TTL_SECONDS)


class HealthStatus(str, Enum):
    """Health check status values."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentHealth:
    """Health check result for a component."""
    
    def __init__(
        self,
        name: str,
        status: HealthStatus,
        latency_ms: Optional[float] = None,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.status = status
        self.latency_ms = latency_ms
        self.message = message
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "name": self.name,
            "status": self.status.value
        }
        if self.latency_ms is not None:
            result["latency_ms"] = round(self.latency_ms, 2)
        if self.message:
            result["message"] = self.message
        if self.details:
            result["details"] = self.details
        return result


async def check_qdrant_health() -> ComponentHealth:
    """Check Qdrant connectivity and status."""
    from qdrant_client import QdrantClient
    from ..utils.patterns import check_component_health
    from ..config import get_settings

    def check_fn():
        settings = get_settings()
        client = QdrantClient(
            url=settings.QDRANT_URL,
            timeout=10,
        )
        try:
            # Lightweight connectivity check — lists all collections
            collections = client.get_collections().collections
            collection_names = [c.name for c in collections]

            # Report point count for the main collection if it exists;
            # a missing collection is normal on a fresh setup (not an error)
            document_count = 0
            if settings.QDRANT_COLLECTION_NAME in collection_names:
                info = client.get_collection(settings.QDRANT_COLLECTION_NAME)
                document_count = info.points_count

            return {"document_count": document_count, "collections": collection_names}
        finally:
            client.close()

    return await check_component_health(
        name="qdrant",
        check_fn=check_fn,
        details_fn=lambda result: result
    )


async def check_llm_health() -> ComponentHealth:
    """Check the configured LLM provider's connectivity and circuit status."""
    start = time.perf_counter()

    try:
        from .lifespan import get_llm_client

        client = get_llm_client()
        if client is None:
            return ComponentHealth(
                name="llm",
                status=HealthStatus.UNHEALTHY,
                message="No LLM client (configure a provider in Settings)"
            )

        # The client declares its own circuit (FallbackLLMClient delegates to
        # its primary). A provider missing `circuit` raises into the outer
        # except — loud failure, not a silent "unknown" state.
        circuit_state = client.circuit.state.value
        latency = (time.perf_counter() - start) * 1000

        cache_status = client.get_cache_status()

        details = {
            "provider": type(client).__name__,
            "model": client.model_main,
            "circuit_state": circuit_state,
            "sqlite_cache_enabled": cache_status.get("cache_enabled", False),
        }

        if circuit_state == "open":
            return ComponentHealth(
                name="llm",
                status=HealthStatus.DEGRADED,
                latency_ms=latency,
                message="Circuit breaker open",
                details=details
            )

        return ComponentHealth(
            name="llm",
            status=HealthStatus.HEALTHY,
            latency_ms=latency,
            details=details
        )
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        logger.error(f"LLM health check failed: {e}", exc_info=True)

        return ComponentHealth(
            name="llm",
            status=HealthStatus.UNHEALTHY,
            latency_ms=latency,
            message="Internal error during health check"
        )


async def check_embeddings_health() -> ComponentHealth:
    """Check embedding provider connectivity (lightweight check)."""
    start = time.perf_counter()

    try:
        settings = get_settings()
        provider = settings.EMBEDDING_PROVIDER

        # Delegate the key-present check to the shared helper so the scoped-key
        # fallback logic lives in exactly one place (adding a new provider only
        # requires updating helpers.py, not this function too).
        from .settings_routes.helpers import embedding_has_api_key

        if not embedding_has_api_key(settings):
            _KEY_HINTS = {
                "voyage": "VOYAGE_API_KEY",
                "cohere": "COHERE_API_KEY",
                "openai": "OPENAI_API_KEY",
            }
            hint = _KEY_HINTS.get(provider, "the provider's API key")
            return ComponentHealth(
                name="embeddings",
                status=HealthStatus.UNHEALTHY,
                message=f"API key not configured for embedding provider '{provider}'. Set it in the Settings UI or via {hint} in .env."
            )
        
        # Check circuit breaker status (only applies to cloud providers)
        from .middleware.circuit_breaker import voyage_circuit
        
        circuit_state = voyage_circuit.state.value
        latency = (time.perf_counter() - start) * 1000
        
        if circuit_state == "open":
            return ComponentHealth(
                name="embeddings",
                status=HealthStatus.DEGRADED,
                latency_ms=latency,
                message="Circuit breaker open",
                details={"circuit_state": circuit_state, "provider": provider}
            )
        
        return ComponentHealth(
            name="embeddings",
            status=HealthStatus.HEALTHY,
            latency_ms=latency,
            details={"circuit_state": circuit_state, "provider": provider, "model": settings.EMBEDDING_MODEL}
        )
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        logger.error(f"Embeddings health check failed: {e}", exc_info=True)
        
        return ComponentHealth(
            name="embeddings",
            status=HealthStatus.UNHEALTHY,
            latency_ms=latency,
            message="Internal error during health check"
        )


async def check_cache_health() -> ComponentHealth:
    """Check cache system status."""
    from .middleware.logging_middleware import get_metrics
    from ..utils.patterns import check_component_health
    
    return await check_component_health(
        name="cache",
        check_fn=get_metrics,
        details_fn=lambda metrics: {
            "cache_hit_rate": metrics.get("cache_hit_rate", 0),
            "request_count": metrics.get("request_count", 0)
        }
    )


async def check_sqlite_cache_health() -> ComponentHealth:
    """Check SQLite query cache connectivity."""
    from ..db.sqlite_cache import get_sqlite_cache
    from ..utils.patterns import check_component_health

    cache = await get_sqlite_cache()
    return await check_component_health(
        name="sqlite_cache",
        check_fn=cache.ping,
        details_fn=lambda result: {"table": "backend_cache", "reachable": bool(result)},
    )


async def run_health_checks() -> Dict[str, Any]:
    """
    Run all health checks and return aggregated status.

    The full dependency sweep is cached for HEALTH_CACHE_TTL_SECONDS.
    On a cache hit, the cached dict is returned as-is (its ``timestamp``
    is the time the sweep ran, so callers can see the cache age). On a
    miss, all component checks run in parallel and the result is stored.
    No lock: a concurrent miss runs at most one extra sweep, which is
    acceptable.

    Returns:
        Health check results
    """
    cached = _health_cache.get("sweep")
    if cached is not None:
        return cached

    start = time.perf_counter()

    # Basic system health
    result = {
        "status": HealthStatus.HEALTHY.value,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": __version__
    }

    # Map check coroutines to their component names for error handling
    check_definitions = [
        ("qdrant", check_qdrant_health()),
        ("llm", check_llm_health()),
        ("embeddings", check_embeddings_health()),
        ("cache", check_cache_health()),
        ("sqlite_cache", check_sqlite_cache_health()),
    ]

    # Run component checks in parallel
    checks = await asyncio.gather(
        *[check for _, check in check_definitions],
        return_exceptions=True
    )

    components = []
    overall_status = HealthStatus.HEALTHY

    for (component_name, _), check in zip(check_definitions, checks):
        if isinstance(check, Exception):
            logger.error(f"Health check failed for {component_name}: {check}", exc_info=True)
            components.append(
                ComponentHealth(
                    name=component_name,
                    status=HealthStatus.UNHEALTHY,
                    message="Check failed"
                ).to_dict()
            )
            overall_status = HealthStatus.UNHEALTHY
        else:
            components.append(check.to_dict())
            if check.status == HealthStatus.UNHEALTHY:
                overall_status = HealthStatus.UNHEALTHY
            elif check.status == HealthStatus.DEGRADED and overall_status != HealthStatus.UNHEALTHY:
                overall_status = HealthStatus.DEGRADED

    result["status"] = overall_status.value
    result["components"] = components

    result["total_latency_ms"] = round((time.perf_counter() - start) * 1000, 2)

    _health_cache["sweep"] = result

    return result


async def liveness_check() -> Dict[str, Any]:
    """
    Simple liveness check for Kubernetes probes.
    Returns immediately if the application is running.
    """
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


async def readiness_check() -> Dict[str, Any]:
    """
    Readiness check for Kubernetes probes and container orchestrators.

    "Ready" means "can answer queries": all critical components
    (retriever, LLM client, orchestrator) finished initializing. It does
    NOT run the dependency sweep — transient dependency failures are
    reported by /health and must not flap the readiness probe.

    Status values:
    - "ready"          — initialization complete
    - "setup_required" — no LLM provider configured yet (first-run setup)
    - "failed"         — initialization finished with errors
    - "initializing"   — still starting up

    Error details are never included: this endpoint is public.
    """
    from .lifespan import get_initialization_status

    init = get_initialization_status()

    if init["complete"]:
        status = "ready"
    elif init["setup_required"]:
        status = "setup_required"
    elif init["errors"]:
        status = "failed"
    else:
        status = "initializing"

    return {
        "ready": status == "ready",
        "status": status,
        "components": init["components"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
