"""
Tests for the cached dependency sweep in run_health_checks() and the
provider-aware check_llm_health() component.
"""
import time
import pytest
from unittest.mock import AsyncMock, patch

import src.api.health as health
from src.api.health import ComponentHealth, HealthStatus
from src.api.middleware.circuit_breaker import CircuitBreaker, CircuitState
from src.query_processing.base_rag_client import BaseRAGClient
from src.query_processing.gemini_client import GeminiClient
from src.query_processing.openai_client import OpenAICompatibleClient


@pytest.fixture(autouse=True)
def _clear_health_cache():
    """Clear the module-level health cache before and after each test."""
    health._health_cache.clear()
    yield
    health._health_cache.clear()


def _healthy(name: str) -> ComponentHealth:
    return ComponentHealth(name=name, status=HealthStatus.HEALTHY)


@pytest.fixture()
def mock_checks():
    """Patch the five dependency checks with counting AsyncMocks."""
    checks = {
        "check_qdrant_health": AsyncMock(return_value=_healthy("qdrant")),
        "check_llm_health": AsyncMock(return_value=_healthy("llm")),
        "check_embeddings_health": AsyncMock(return_value=_healthy("embeddings")),
        "check_cache_health": AsyncMock(return_value=_healthy("cache")),
        "check_sqlite_cache_health": AsyncMock(return_value=_healthy("sqlite_cache")),
    }
    with patch.multiple(
        health,
        **checks,
    ):
        yield checks


@pytest.mark.asyncio
async def test_sweep_cached_within_ttl(mock_checks):
    """Two calls within the TTL run each dependency check only once."""
    first = await health.run_health_checks()
    second = await health.run_health_checks()

    for name, mock in mock_checks.items():
        assert mock.await_count == 1, name

    assert first == second
    assert first["timestamp"] == second["timestamp"]


@pytest.mark.asyncio
async def test_cache_clear_reruns_sweep(mock_checks):
    """Clearing the cache forces a fresh dependency sweep."""
    await health.run_health_checks()
    health._health_cache.clear()
    await health.run_health_checks()

    for name, mock in mock_checks.items():
        assert mock.await_count == 2, name


@pytest.mark.asyncio
async def test_failing_check_marks_overall_unhealthy(mock_checks):
    """A check that raises marks its component and overall status unhealthy."""
    mock_checks["check_qdrant_health"].side_effect = RuntimeError("boom")

    result = await health.run_health_checks()

    assert result["status"] == "unhealthy"
    qdrant = next(c for c in result["components"] if c["name"] == "qdrant")
    assert qdrant["status"] == "unhealthy"
    assert qdrant["message"] == "Check failed"


# ---------------------------------------------------------------------------
# check_llm_health() — provider-aware LLM component
# ---------------------------------------------------------------------------


def _open_circuit(name: str) -> CircuitBreaker:
    """A real CircuitBreaker forced OPEN (fresh failure time, won't half-open)."""
    breaker = CircuitBreaker(name)
    breaker._state = CircuitState.OPEN
    breaker._stats.last_failure_time = time.time()
    return breaker


def _openai_like_client(circuit: CircuitBreaker) -> OpenAICompatibleClient:
    """OpenAICompatibleClient instance without __init__ (no SDK/network needed).

    ``object.__new__`` keeps ``type(client).__name__ == "OpenAICompatibleClient"``
    so the provider detail assertion stays meaningful.
    """
    client = object.__new__(OpenAICompatibleClient)
    client._circuit = circuit
    client._model_main = "gpt-x"
    client.get_cache_status = lambda: {"cache_enabled": True, "model": "gpt-x"}
    return client


@pytest.mark.asyncio
async def test_llm_health_no_client_unhealthy():
    """No LLM client configured → unhealthy."""
    with patch("src.api.lifespan.get_llm_client", return_value=None):
        result = await health.check_llm_health()

    assert result.name == "llm"
    assert result.status == HealthStatus.UNHEALTHY
    assert result.message == "No LLM client (configure a provider in Settings)"


@pytest.mark.asyncio
async def test_llm_health_openai_client_healthy(monkeypatch):
    """OpenAI-compatible client with a closed circuit → healthy.

    Regression test: the old gemini-only check marked non-Gemini users
    unhealthy because GEMINI_API_KEY was unset.
    """
    monkeypatch.setenv("GEMINI_API_KEY", "")
    client = _openai_like_client(CircuitBreaker("openai_compat_test"))

    with patch("src.api.lifespan.get_llm_client", return_value=client):
        result = await health.check_llm_health()

    assert result.status == HealthStatus.HEALTHY
    assert result.details["provider"] == "OpenAICompatibleClient"
    assert result.details["model"] == "gpt-x"
    assert result.details["circuit_state"] == "closed"
    assert result.details["sqlite_cache_enabled"] is True


@pytest.mark.asyncio
async def test_llm_health_gemini_circuit_open_degraded():
    """Gemini client with the shared gemini_circuit open → degraded."""
    client = object.__new__(GeminiClient)
    client._model_main = "gemini-x"
    client._sqlite_cache = None

    with patch("src.api.lifespan.get_llm_client", return_value=client), \
         patch("src.query_processing.gemini_client.gemini_circuit", _open_circuit("gemini_api")):
        result = await health.check_llm_health()

    assert result.status == HealthStatus.DEGRADED
    assert result.message == "Circuit breaker open"
    assert result.details["circuit_state"] == "open"
    assert result.details["provider"] == "GeminiClient"


@pytest.mark.asyncio
async def test_llm_health_fallback_uses_primary_circuit():
    """FallbackLLMClient reports its primary's circuit — open → degraded."""
    from src.query_processing.fallback_llm_client import FallbackLLMClient

    primary = _openai_like_client(_open_circuit("openai_compat_primary"))
    fallback = _openai_like_client(CircuitBreaker("openai_compat_fallback"))
    client = FallbackLLMClient(primary, fallback)

    with patch("src.api.lifespan.get_llm_client", return_value=client):
        result = await health.check_llm_health()

    assert result.status == HealthStatus.DEGRADED
    assert result.details["circuit_state"] == "open"
    assert result.details["provider"] == "FallbackLLMClient"


@pytest.mark.asyncio
async def test_llm_health_client_without_circuit_fails_loudly():
    """A provider missing `circuit` must not silently report healthy."""

    class _NoCircuitClient(BaseRAGClient):
        @property
        def model_main(self):
            return "proto-model"

    client = _NoCircuitClient()

    with patch("src.api.lifespan.get_llm_client", return_value=client):
        result = await health.check_llm_health()

    assert result.status == HealthStatus.UNHEALTHY
    assert result.message == "Internal error during health check"


# ---------------------------------------------------------------------------
# readiness_check() — "ready" means "can answer queries"
# ---------------------------------------------------------------------------


_COMPONENTS = {
    "retriever": True,
    "llm_client": True,
    "rag_orchestrator": True,
    "citation_manager": True,
}


def _init_status(complete: bool, setup_required: bool = False, errors=None, components=None):
    return {
        "complete": complete,
        "setup_required": setup_required,
        "errors": errors or [],
        "components": components or dict(_COMPONENTS),
    }


@pytest.mark.asyncio
async def test_readiness_ready():
    """Initialization complete → ready."""
    with patch("src.api.lifespan.get_initialization_status", return_value=_init_status(complete=True)):
        result = await health.readiness_check()

    assert result["ready"] is True
    assert result["status"] == "ready"
    assert result["components"] == _COMPONENTS
    assert "errors" not in result


@pytest.mark.asyncio
async def test_readiness_ready_wins_over_setup_flag():
    """complete=True beats a stale setup_required flag → ready."""
    init = _init_status(complete=True, setup_required=True)

    with patch("src.api.lifespan.get_initialization_status", return_value=init):
        result = await health.readiness_check()

    assert result["ready"] is True
    assert result["status"] == "ready"


@pytest.mark.asyncio
async def test_readiness_setup_required():
    """Not complete and setup_required flag set → setup_required."""
    init = _init_status(complete=False, setup_required=True)

    with patch("src.api.lifespan.get_initialization_status", return_value=init):
        result = await health.readiness_check()

    assert result["ready"] is False
    assert result["status"] == "setup_required"
    assert result["components"] == _COMPONENTS
    assert "errors" not in result


@pytest.mark.asyncio
async def test_readiness_failed_hides_error_details():
    """LLM configured but init errors → failed, without leaking error text."""
    secret_looking = "init failed: GEMINI_API_KEY=sk-secret-12345 rejected"
    init = _init_status(complete=False, errors=[{"component": "llm_client", "error": secret_looking}])

    with patch("src.api.lifespan.get_initialization_status", return_value=init):
        result = await health.readiness_check()

    assert result["ready"] is False
    assert result["status"] == "failed"
    assert result["components"] == _COMPONENTS
    assert "errors" not in result
    assert secret_looking not in str(result)
    assert "sk-secret-12345" not in str(result)


@pytest.mark.asyncio
async def test_readiness_initializing():
    """Configured, not complete, no errors → still initializing."""
    with patch("src.api.lifespan.get_initialization_status", return_value=_init_status(complete=False)):
        result = await health.readiness_check()

    assert result["ready"] is False
    assert result["status"] == "initializing"
    assert result["components"] == _COMPONENTS
    assert "errors" not in result
