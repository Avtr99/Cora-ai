"""
Tests for hot_swap_llm_client() completing deferred initialization when the
app booted in setup mode (no LLM configured at startup).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import src.api.lifespan as lifespan


@pytest.fixture()
def setup_mode(monkeypatch):
    """Simulate a boot where the retriever initialized but no LLM existed."""
    monkeypatch.setattr(lifespan, "retriever", object())
    monkeypatch.setattr(lifespan, "llm_client", None)
    monkeypatch.setattr(lifespan, "rag_orchestrator", None)
    monkeypatch.setattr(lifespan, "initialization_complete", False)
    monkeypatch.setattr(lifespan, "setup_required", True)
    lifespan.initialization_errors.clear()
    yield
    lifespan.initialization_errors.clear()


def _patch_hot_swap(job_manager):
    """Patch everything hot_swap_llm_client/_finalize_initialization touch."""
    new_client = MagicMock()
    new_client.model_main = "gpt-x"

    return patch.multiple(
        lifespan,
        is_llm_configured=MagicMock(return_value=True),
        create_llm_client=MagicMock(return_value=new_client),
        get_async_query_job_manager=MagicMock(return_value=job_manager),
    ), new_client


def _job_manager():
    manager = MagicMock()
    manager.configure = AsyncMock()
    manager.start = AsyncMock()
    return manager


@pytest.mark.asyncio
async def test_hot_swap_completes_deferred_initialization(setup_mode):
    """First successful hot-swap in setup mode finalizes initialization."""
    job_manager = _job_manager()
    patches, new_client = _patch_hot_swap(job_manager)
    sentinel_cache = MagicMock(name="sqlite_cache")

    with patches, \
         patch("src.agents.streaming_orchestrator.StreamingRAGOrchestrator.create",
               new=AsyncMock(return_value=object())), \
         patch("src.db.sqlite_cache.get_sqlite_cache", new=AsyncMock(return_value=sentinel_cache)), \
         patch("src.retrieval.schema_discovery.discover_fields_from_payloads"):
        result = await lifespan.hot_swap_llm_client()

    assert result["success"] is True
    assert lifespan.initialization_complete is True
    assert lifespan.setup_required is False
    job_manager.start.assert_awaited_once()
    # The client owns cache attachment — exactly once, and not re-done by finalize.
    new_client.attach_sqlite_cache.assert_called_once_with(sentinel_cache)


@pytest.mark.asyncio
async def test_second_hot_swap_does_not_restart_job_manager(setup_mode):
    """A second hot-swap skips finalize — initialization_complete is already True."""
    job_manager = _job_manager()
    patches, _ = _patch_hot_swap(job_manager)

    with patches, \
         patch("src.agents.streaming_orchestrator.StreamingRAGOrchestrator.create",
               new=AsyncMock(return_value=object())), \
         patch("src.db.sqlite_cache.get_sqlite_cache", new=AsyncMock(return_value=None)), \
         patch("src.retrieval.schema_discovery.discover_fields_from_payloads"):
        first = await lifespan.hot_swap_llm_client()
        second = await lifespan.hot_swap_llm_client()

    assert first["success"] is True
    assert second["success"] is True
    assert lifespan.initialization_complete is True
    assert lifespan.setup_required is False
    assert job_manager.start.await_count == 1


@pytest.mark.asyncio
async def test_hot_swap_without_retriever_does_not_finalize(setup_mode, monkeypatch):
    """No retriever → orchestrator can't be built → finalize stays skipped."""
    monkeypatch.setattr(lifespan, "retriever", None)
    job_manager = _job_manager()
    patches, _ = _patch_hot_swap(job_manager)

    with patches, \
         patch("src.agents.streaming_orchestrator.StreamingRAGOrchestrator.create",
               new=AsyncMock(return_value=object())), \
         patch("src.db.sqlite_cache.get_sqlite_cache", new=AsyncMock(return_value=None)), \
         patch("src.retrieval.schema_discovery.discover_fields_from_payloads"):
        result = await lifespan.hot_swap_llm_client()

    assert result["success"] is True
    assert lifespan.initialization_complete is False
    job_manager.start.assert_not_awaited()
