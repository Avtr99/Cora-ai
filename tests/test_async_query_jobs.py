import asyncio

import pytest

from src.api.async_query_jobs import (
    MAX_PAYLOAD_BYTES,
    AsyncQueryJobManager,
)


async def _wait_for_terminal_status(
    manager: AsyncQueryJobManager,
    job_id: str,
    timeout_seconds: float = 3.0,
) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < deadline:
        job = await manager.get_job(job_id)
        if job and job["status"] in {"completed", "failed"}:
            return job
        await asyncio.sleep(0.05)
    raise AssertionError(f"Job {job_id} did not reach terminal status within timeout")


@pytest.mark.asyncio
async def test_async_query_job_manager_completes_job():
    manager = AsyncQueryJobManager(max_queue_size=5, job_ttl_seconds=60)

    async def processor(payload: dict, job_id: str) -> dict:
        await asyncio.sleep(0.01)
        return {"echo": payload["text"], "job_id": job_id}

    manager.register_processor(processor)
    await manager.start(worker_count=1)

    try:
        accepted = await manager.enqueue({"text": "hello"})
        job = await _wait_for_terminal_status(manager, accepted["job_id"])

        assert accepted["status"] == "queued"
        assert job["status"] == "completed"
        assert job["result"]["echo"] == "hello"
        assert job["error"] is None
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_async_query_job_manager_marks_failed_job():
    manager = AsyncQueryJobManager(max_queue_size=5, job_ttl_seconds=60)

    async def processor(payload: dict, job_id: str) -> dict:
        raise RuntimeError("boom")

    manager.register_processor(processor)
    await manager.start(worker_count=1)

    try:
        accepted = await manager.enqueue({"text": "hello"})
        job = await _wait_for_terminal_status(manager, accepted["job_id"])

        assert job["status"] == "failed"
        assert job["result"] is None
        assert job["error"] == "Internal error processing query"
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_async_query_job_manager_rejects_oversized_payload():
    manager = AsyncQueryJobManager(max_queue_size=5, job_ttl_seconds=60)

    async def processor(payload: dict, job_id: str) -> dict:
        return {"ok": True}

    manager.register_processor(processor)
    await manager.start(worker_count=1)

    oversized_payload = {"text": "x" * (MAX_PAYLOAD_BYTES + 1)}

    try:
        with pytest.raises(ValueError, match="payload exceeds"):
            await manager.enqueue(oversized_payload)
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_async_query_job_manager_rejects_when_queue_full():
    manager = AsyncQueryJobManager(max_queue_size=1, job_ttl_seconds=60)

    gate = asyncio.Event()

    async def processor(payload: dict, job_id: str) -> dict:
        await gate.wait()
        return {"ok": True}

    manager.register_processor(processor)
    await manager.start(worker_count=1)

    try:
        first = await manager.enqueue({"text": "first"})

        # Wait until first job is picked up by worker and queue can fill with second.
        deadline = asyncio.get_event_loop().time() + 2.0
        processing_job = None
        while asyncio.get_event_loop().time() < deadline:
            job = await manager.get_job(first["job_id"])
            if job and job["status"] == "processing":
                processing_job = job
                break
            await asyncio.sleep(0.05)

        assert processing_job is not None and processing_job["status"] == "processing", (
            f"Job {first['job_id']} did not reach processing state before queue-full assertion"
        )

        await manager.enqueue({"text": "second"})

        with pytest.raises(asyncio.QueueFull):
            await manager.enqueue({"text": "third"})
    finally:
        gate.set()
        await manager.stop()
