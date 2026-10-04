import asyncio

import pytest

from src.api.async_query_jobs import (
    MAX_PAYLOAD_BYTES,
    AsyncQueryJobManager,
)
from src.config import reset_settings_singleton
from src.db.database import get_connection, run_migrations


@pytest.fixture(autouse=True)
def _isolated_async_db(tmp_path, monkeypatch):
    """Point each async-job test at its own migrated SQLite file."""
    db_path = tmp_path / "async_query_jobs.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    reset_settings_singleton()
    run_migrations()
    yield
    reset_settings_singleton()


async def _wait_for_terminal_status(
    manager: AsyncQueryJobManager,
    job_id: str,
    timeout_seconds: float = 3.0,
    user_id: str = "owner",
) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < deadline:
        job = await manager.get_job(job_id, user_id)
        if job and job["status"] in {"completed", "failed"}:
            return job
        await asyncio.sleep(0.05)
    raise AssertionError(f"Job {job_id} did not reach terminal status within timeout")


async def _wait_for_status(
    manager: AsyncQueryJobManager,
    job_id: str,
    status: str,
    timeout_seconds: float = 3.0,
    user_id: str = "owner",
) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < deadline:
        job = await manager.get_job(job_id, user_id)
        if job and job["status"] == status:
            return job
        await asyncio.sleep(0.05)
    raise AssertionError(f"Job {job_id} did not reach status {status} within timeout")


@pytest.mark.asyncio
async def test_async_query_job_manager_completes_job():
    manager = AsyncQueryJobManager(max_queue_size=5, job_ttl_seconds=60)

    async def processor(payload: dict, job_id: str, user_id: str) -> dict:
        await asyncio.sleep(0.01)
        return {"echo": payload["text"], "job_id": job_id, "user_id": user_id}

    manager.register_processor(processor)
    await manager.start(worker_count=1)

    try:
        accepted = await manager.enqueue({"text": "hello"}, user_id="owner")
        job = await _wait_for_terminal_status(manager, accepted["job_id"])

        assert accepted["status"] == "queued"
        assert job["status"] == "completed"
        assert job["result"]["echo"] == "hello"
        assert job["result"]["user_id"] == "owner"
        assert job["error"] is None
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_async_query_job_manager_marks_failed_job():
    manager = AsyncQueryJobManager(max_queue_size=5, job_ttl_seconds=60)

    async def processor(payload: dict, job_id: str, user_id: str) -> dict:
        raise RuntimeError("boom")

    manager.register_processor(processor)
    await manager.start(worker_count=1)

    try:
        accepted = await manager.enqueue({"text": "hello"}, user_id="owner")
        job = await _wait_for_terminal_status(manager, accepted["job_id"])

        assert job["status"] == "failed"
        assert job["result"] is None
        assert job["error"] == "Internal error processing query"
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_async_query_job_manager_rejects_oversized_payload():
    manager = AsyncQueryJobManager(max_queue_size=5, job_ttl_seconds=60)

    async def processor(payload: dict, job_id: str, user_id: str) -> dict:
        return {"ok": True}

    manager.register_processor(processor)
    await manager.start(worker_count=1)

    oversized_payload = {"text": "x" * (MAX_PAYLOAD_BYTES + 1)}

    try:
        with pytest.raises(ValueError, match="payload exceeds"):
            await manager.enqueue(oversized_payload, user_id="owner")
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_async_query_job_manager_rejects_when_queue_full():
    manager = AsyncQueryJobManager(max_queue_size=1, job_ttl_seconds=60)

    gate = asyncio.Event()

    async def processor(payload: dict, job_id: str, user_id: str) -> dict:
        await gate.wait()
        return {"ok": True}

    manager.register_processor(processor)
    await manager.start(worker_count=1)

    try:
        first = await manager.enqueue({"text": "first"}, user_id="owner")

        # Wait until first job is picked up by worker and queue can fill with second.
        deadline = asyncio.get_event_loop().time() + 2.0
        processing_job = None
        while asyncio.get_event_loop().time() < deadline:
            job = await manager.get_job(first["job_id"], "owner")
            if job and job["status"] == "processing":
                processing_job = job
                break
            await asyncio.sleep(0.05)

        assert processing_job is not None and processing_job["status"] == "processing", (
            f"Job {first['job_id']} did not reach processing state before queue-full assertion"
        )

        await manager.enqueue({"text": "second"}, user_id="owner")

        with pytest.raises(asyncio.QueueFull):
            await manager.enqueue({"text": "third"}, user_id="owner")
    finally:
        gate.set()
        await manager.stop()


@pytest.mark.asyncio
async def test_resumes_queued_jobs_after_restart():
    """A queued job still waiting when the manager stops is resumed by a new instance."""
    manager1 = AsyncQueryJobManager(max_queue_size=5, job_ttl_seconds=60)
    gate1 = asyncio.Event()

    async def slow_processor(payload: dict, job_id: str, user_id: str) -> dict:
        await gate1.wait()
        return {"ok": True}

    manager1.register_processor(slow_processor)
    await manager1.start(worker_count=1)

    try:
        first = await manager1.enqueue({"text": "first"}, user_id="owner")
        await _wait_for_status(manager1, first["job_id"], "processing")

        # While the worker is busy, a second job stays queued in the DB.
        second = await manager1.enqueue({"text": "hello"}, user_id="owner")
        second_before = await manager1.get_job(second["job_id"], "owner")
        assert second_before is not None and second_before["status"] == "queued"
    finally:
        await manager1.stop()
        gate1.set()

    manager2 = AsyncQueryJobManager(max_queue_size=5, job_ttl_seconds=60)

    async def processor(payload: dict, job_id: str, user_id: str) -> dict:
        return {"echo": payload["text"], "job_id": job_id}

    manager2.register_processor(processor)
    await manager2.start(worker_count=1)

    try:
        job = await _wait_for_terminal_status(manager2, second["job_id"])
        assert job["status"] == "completed"
        assert job["result"]["echo"] == "hello"
    finally:
        await manager2.stop()


@pytest.mark.asyncio
async def test_interrupted_processing_marked_failed_on_restart():
    """A processing job at shutdown is marked failed when the manager restarts."""
    manager1 = AsyncQueryJobManager(max_queue_size=5, job_ttl_seconds=60)
    gate = asyncio.Event()

    async def processor(payload: dict, job_id: str, user_id: str) -> dict:
        await gate.wait()
        return {"ok": True}

    manager1.register_processor(processor)
    await manager1.start(worker_count=1)

    try:
        accepted = await manager1.enqueue({"text": "hello"}, user_id="owner")
        await _wait_for_status(manager1, accepted["job_id"], "processing")
    finally:
        await manager1.stop()
        gate.set()

    manager2 = AsyncQueryJobManager(max_queue_size=5, job_ttl_seconds=60)

    async def completing_processor(payload: dict, job_id: str, user_id: str) -> dict:
        return {"ok": True}

    manager2.register_processor(completing_processor)
    await manager2.start(worker_count=1)

    try:
        job = await _wait_for_terminal_status(manager2, accepted["job_id"])
        assert job["status"] == "failed"
        assert "interrupted by restart" in (job["error"] or "").lower()
    finally:
        await manager2.stop()


@pytest.mark.asyncio
async def test_idempotent_enqueue_returns_existing_job():
    """Same client_request_id returns the original job without creating a duplicate."""
    manager = AsyncQueryJobManager(max_queue_size=5, job_ttl_seconds=60)

    async def processor(payload: dict, job_id: str, user_id: str) -> dict:
        await asyncio.sleep(0.01)
        return {"ok": True}

    manager.register_processor(processor)
    await manager.start(worker_count=1)

    try:
        first = await manager.enqueue(
            {"text": "hello", "client_request_id": "client-123"},
            user_id="owner",
        )
        second = await manager.enqueue(
            {"text": "hello", "client_request_id": "client-123"},
            user_id="owner",
        )

        assert first["job_id"] == second["job_id"]
        assert second["status"] in {"queued", "processing", "completed"}

        # Only one queued/completed job should exist for this idempotency key.
        assert manager._queue.qsize() <= 1
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_idempotent_enqueue_is_scoped_per_user():
    """The same client_request_id under different users gives different jobs."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (id, username, role) VALUES ('m1', 'm1', 'member')"
        )
        conn.commit()
    finally:
        conn.close()

    manager = AsyncQueryJobManager(max_queue_size=5, job_ttl_seconds=60)

    async def processor(payload: dict, job_id: str, user_id: str) -> dict:
        await asyncio.sleep(0.01)
        return {"ok": True}

    manager.register_processor(processor)
    await manager.start(worker_count=1)

    try:
        owner_first = await manager.enqueue(
            {"text": "hello", "client_request_id": "k1"}, user_id="owner"
        )
        member_job = await manager.enqueue(
            {"text": "hello", "client_request_id": "k1"}, user_id="m1"
        )
        owner_second = await manager.enqueue(
            {"text": "hello", "client_request_id": "k1"}, user_id="owner"
        )

        assert member_job["job_id"] != owner_first["job_id"]
        assert owner_second["job_id"] == owner_first["job_id"]

        # Status lookup is user-scoped: a member cannot see the owner's job.
        assert await manager.get_job(owner_first["job_id"], "m1") is None
        assert await manager.get_job(owner_first["job_id"], "owner") is not None
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_expired_jobs_are_pruned():
    """Terminal jobs are deleted once their TTL passes."""
    manager = AsyncQueryJobManager(max_queue_size=5, job_ttl_seconds=1)

    async def processor(payload: dict, job_id: str, user_id: str) -> dict:
        return {"ok": True}

    manager.register_processor(processor)
    await manager.start(worker_count=1)

    try:
        accepted = await manager.enqueue({"text": "hello"}, user_id="owner")
        job = await _wait_for_terminal_status(manager, accepted["job_id"])
        assert job["status"] == "completed"

        await asyncio.sleep(1.1)
        await manager._cleanup_expired_jobs()

        assert await manager.get_job(accepted["job_id"], "owner") is None
    finally:
        await manager.stop()
