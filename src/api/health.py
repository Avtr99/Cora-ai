"""
Comprehensive health check endpoints for monitoring system components.
Checks Qdrant, external API connectivity, and cache status.
"""
import time
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from enum import Enum
from loguru import logger

from ..config import get_settings


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


async def check_gemini_health() -> ComponentHealth:
    """Check Gemini API connectivity and context cache status."""
    start = time.perf_counter()
    
    try:
        settings = get_settings()
        
        if not settings.GEMINI_API_KEY:
            return ComponentHealth(
                name="gemini_api",
                status=HealthStatus.UNHEALTHY,
                message="GEMINI_API_KEY not configured"
            )
        
        # Check circuit breaker status
        from .middleware.circuit_breaker import gemini_circuit
        
        circuit_state = gemini_circuit.state.value
        latency = (time.perf_counter() - start) * 1000
        
        # Get context cache status from singleton client
        cache_status = {}
        try:
            from .lifespan import get_gemini_client
            client = get_gemini_client()
            if client and hasattr(client, "get_cache_status"):
                cache_status = client.get_cache_status()
            else:
                cache_status = {"cache_enabled": False, "error": "LLM client not initialized"}
        except Exception:
            cache_status = {"cache_enabled": False, "error": "Could not get cache status"}
        
        if circuit_state == "open":
            return ComponentHealth(
                name="gemini_api",
                status=HealthStatus.DEGRADED,
                latency_ms=latency,
                message="Circuit breaker open",
                details={
                    "circuit_state": circuit_state,
                    "context_cache": cache_status
                }
            )
        
        return ComponentHealth(
            name="gemini_api",
            status=HealthStatus.HEALTHY,
            latency_ms=latency,
            details={
                "circuit_state": circuit_state,
                "model": cache_status.get("model", "unknown"),
                "context_cache_enabled": cache_status.get("cache_enabled", False),
            }
        )
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        logger.error(f"Gemini health check failed: {e}", exc_info=True)
        
        return ComponentHealth(
            name="gemini_api",
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
        
        # Validate that the configured provider has its required credentials
        if provider == "voyage" and not settings.VOYAGE_API_KEY:
            return ComponentHealth(
                name="embeddings",
                status=HealthStatus.UNHEALTHY,
                message="VOYAGE_API_KEY not configured (EMBEDDING_PROVIDER=voyage)"
            )
        elif provider == "cohere" and not settings.COHERE_API_KEY:
            return ComponentHealth(
                name="embeddings",
                status=HealthStatus.UNHEALTHY,
                message="COHERE_API_KEY not configured (EMBEDDING_PROVIDER=cohere)"
            )
        elif provider == "openai" and not settings.OPENAI_API_KEY:
            return ComponentHealth(
                name="embeddings",
                status=HealthStatus.UNHEALTHY,
                message="OPENAI_API_KEY not configured (EMBEDDING_PROVIDER=openai)"
            )
        elif provider == "ollama":
            # Ollama runs locally — no API key needed, just check it's reachable
            pass
        
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

    return await check_component_health(
        name="sqlite_cache",
        check_fn=get_sqlite_cache().ping,
        details_fn=lambda result: {"table": "backend_cache", "reachable": bool(result)},
    )


async def run_health_checks(include_dependencies: bool = True) -> Dict[str, Any]:
    """
    Run all health checks and return aggregated status.
    
    Args:
        include_dependencies: Include external service checks
        
    Returns:
        Health check results
    """
    start = time.perf_counter()
    
    # Basic system health
    result = {
        "status": HealthStatus.HEALTHY.value,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0"
    }
    
    if include_dependencies:
        # Map check coroutines to their component names for error handling
        check_definitions = [
            ("qdrant", check_qdrant_health()),
            ("gemini_api", check_gemini_health()),
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
    Readiness check for Kubernetes probes.
    Checks if the application is ready to receive traffic.
    
    This checks both:
    1. Component initialization status (retriever, gemini_client initialized)
    2. External dependency health (Qdrant, APIs)
    """
    from .lifespan import get_initialization_status
    
    init_status = get_initialization_status()
    
    # First check: Are critical components initialized?
    if not init_status["complete"]:
        return {
            "ready": False,
            "status": "initializing",
            "message": "Service components still initializing",
            "components": init_status["components"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    # Second check: Are external dependencies healthy?
    result = await run_health_checks(include_dependencies=True)
    
    # Consider unhealthy components for readiness
    is_ready = result["status"] != HealthStatus.UNHEALTHY.value
    
    return {
        "ready": is_ready,
        "status": result["status"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
