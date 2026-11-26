import asyncio
import sqlite3
from threading import Event

import pytest

from src.api.async_query_jobs import (
    MAX_PAYLOAD_BYTES,
    AsyncQueryJobManager,
)
from src.config import reset_settings_singleton
from src.db import async_query_jobs as job_store
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
async def test_idempotent_enqueue_after_failure_creates_new_job():
    """A retry with the same client_request_id after a failure is not pinned to the dead job."""
    manager = AsyncQueryJobManager(max_queue_size=5, job_ttl_seconds=60)

    async def processor(payload: dict, job_id: str, user_id: str) -> dict:
        raise RuntimeError("boom")

    manager.register_processor(processor)
    await manager.start(worker_count=1)

    try:
        first = await manager.enqueue(
            {"text": "hello", "client_request_id": "client-fail"},
            user_id="owner",
        )
        await _wait_for_terminal_status(manager, first["job_id"])

        second = await manager.enqueue(
            {"text": "hello", "client_request_id": "client-fail"},
            user_id="owner",
        )
        assert second["job_id"] != first["job_id"]
        assert second["status"] == "queued"
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


@pytest.mark.asyncio
async def test_worker_task_respawns_after_unhandled_failure(monkeypatch):
    """A worker task killed by ANY unhandled error must be replaced while the manager runs."""
    manager = AsyncQueryJobManager(max_queue_size=5, job_ttl_seconds=60)
    calls = []

    async def processor(payload: dict, job_id: str, user_id: str) -> dict:
        calls.append(job_id)
        return {"ok": True}

    manager.register_processor(processor)
    await manager.start(worker_count=1)
    original_worker = manager._workers[0]

    # Kill the worker via a path outside the job-failure handler: make the
    # queue read itself raise once, so the exception escapes _worker_loop.
    real_get = manager._queue.get
    poisoned = {"done": False}

    async def flaky_get():
        if not poisoned["done"]:
            poisoned["done"] = True
            raise RuntimeError("queue backend lost")
        return await real_get()

    monkeypatch.setattr(manager._queue, "get", flaky_get)

    try:
        deadline = asyncio.get_event_loop().time() + 3.0
        while asyncio.get_event_loop().time() < deadline:
            if (
                len(manager._workers) == 1
                and manager._workers[0] is not original_worker
                and original_worker.done()
                and isinstance(original_worker.exception(), RuntimeError)
            ):
                break
            await asyncio.sleep(0.05)
        else:
            raise AssertionError("dead worker was not replaced")

        # The replacement worker drains new jobs; the service keeps working.
        accepted = await manager.enqueue({"text": "two"}, user_id="owner")
        job = await _wait_for_terminal_status(manager, accepted["job_id"])
        assert job["status"] == "completed"
        assert len(calls) == 1
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_fail_job_store_error_does_not_kill_worker(monkeypatch):
    """A busy SQLite writer delays completion without losing the job outcome."""
    manager = AsyncQueryJobManager(max_queue_size=5, job_ttl_seconds=60)
    calls = []

    async def processor(payload: dict, job_id: str, user_id: str) -> dict:
        calls.append(job_id)
        if len(calls) == 1:
            raise RuntimeError("boom")
        return {"ok": True}

    manager.register_processor(processor)
    await manager.start(worker_count=1)

    finish_job = job_store.finish_job
    attempts = 0

    def fail_once(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            exc = sqlite3.OperationalError("database is locked")
            exc.sqlite_errorcode = sqlite3.SQLITE_BUSY
            raise exc
        return finish_job(*args, **kwargs)

    monkeypatch.setattr(job_store, "finish_job", fail_once)

    try:
        first = await manager.enqueue({"text": "one"}, user_id="owner")
        second = await manager.enqueue({"text": "two"}, user_id="owner")

        job = await _wait_for_terminal_status(manager, second["job_id"])
        assert job["status"] == "completed"
        failed = await manager.get_job(first["job_id"], "owner")
        assert failed["status"] == "failed"
        assert len(calls) == 2
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_per_caller_queue_bound_does_not_starve_other_callers():
    """One caller can hold at most the per-caller bound; another caller still gets in."""
    manager = AsyncQueryJobManager(max_queue_size=5, job_ttl_seconds=60, per_caller_queue_max=2)

    gate = asyncio.Event()

    async def processor(payload: dict, job_id: str, user_id: str) -> dict:
        await gate.wait()
        return {"ok": True}

    manager.register_processor(processor)
    await manager.start(worker_count=1)

    try:
        await manager.enqueue({"text": "a1"}, user_id="owner", caller="1.1.1.1")
        await manager.enqueue({"text": "a2"}, user_id="owner", caller="1.1.1.1")
        await manager.enqueue({"text": "a3"}, user_id="owner", caller="1.1.1.1")

        # Caller 'a' has hit its bound: 1 processing + 2 queued... bound counts
        # jobs not yet consumed by the worker, so the third enqueue was already
        # at the bound only if the worker has not claimed. Let the worker claim.
        await asyncio.sleep(0.2)

        with pytest.raises(asyncio.QueueFull):
            await manager.enqueue({"text": "a4"}, user_id="owner", caller="1.1.1.1")

        # A different caller is not denied by 'a's held slots.
        other = await manager.enqueue({"text": "b1"}, user_id="owner", caller="2.2.2.2")
        assert other["status"] == "queued"

        gate.set()
        job = await _wait_for_terminal_status(manager, other["job_id"])
        assert job["status"] == "completed"
    finally:
        gate.set()
        await manager.stop()


@pytest.mark.asyncio
async def test_per_caller_capacity_tracks_dequeue_during_insert(monkeypatch):
    manager = AsyncQueryJobManager(max_queue_size=5, per_caller_queue_max=2)
    first_started = asyncio.Event()
    second_started = asyncio.Event()
    release_first = asyncio.Event()
    release_second = asyncio.Event()
    insert_started = asyncio.Event()
    release_insert = Event()
    loop = asyncio.get_running_loop()

    async def processor(payload, job_id, user_id):
        if payload["text"] == "first":
            first_started.set()
            await release_first.wait()
        elif payload["text"] == "second":
            second_started.set()
            await release_second.wait()
        return {"ok": True}

    create_job = job_store.create_job

    def gated_create(job_id, payload, *args):
        if payload["text"] == "third":
            loop.call_soon_threadsafe(insert_started.set)
            assert release_insert.wait(timeout=3)
        return create_job(job_id, payload, *args)

    monkeypatch.setattr(job_store, "create_job", gated_create)
    manager.register_processor(processor)
    await manager.start()
    try:
        await manager.enqueue({"text": "first"}, user_id="owner")
        await asyncio.wait_for(first_started.wait(), timeout=3)
        await manager.enqueue({"text": "second"}, user_id="owner")
        third = asyncio.create_task(manager.enqueue({"text": "third"}, user_id="owner"))
        try:
            await asyncio.wait_for(insert_started.wait(), timeout=3)
            release_first.set()
            await asyncio.wait_for(second_started.wait(), timeout=3)
        finally:
            release_insert.set()
            await third
        fourth = await manager.enqueue({"text": "fourth"}, user_id="owner")
        assert fourth["status"] == "queued"
    finally:
        release_first.set()
        release_second.set()
        await manager.stop()


@pytest.mark.asyncio
async def test_terminal_write_error_retains_result_and_defers_ack(monkeypatch):
    """Non-lock finish_job failure retries without rerunning processor and acks once on success."""
    manager = AsyncQueryJobManager(max_queue_size=5, job_ttl_seconds=60)
    processor_calls = 0

    async def processor(payload: dict, job_id: str, user_id: str) -> dict:
        nonlocal processor_calls
        processor_calls += 1
        return {"echo": payload["text"], "run": processor_calls}

    manager.register_processor(processor)
    await manager.start(worker_count=1)

    real_finish_job = job_store.finish_job
    first_write_failed = asyncio.Event()
    allow_write_succeed = Event()
    loop = asyncio.get_running_loop()
    write_attempts = 0

    def flaky_finish(*args, **kwargs):
        nonlocal write_attempts
        write_attempts += 1
        if write_attempts == 1:
            loop.call_soon_threadsafe(first_write_failed.set)
            raise RuntimeError("transient storage error")
        assert allow_write_succeed.wait(timeout=3)
        return real_finish_job(*args, **kwargs)

    real_task_done = manager._queue.task_done
    ack_calls = 0

    def tracked_task_done():
        nonlocal ack_calls
        ack_calls += 1
        real_task_done()

    monkeypatch.setattr(job_store, "finish_job", flaky_finish)
    monkeypatch.setattr(manager._queue, "task_done", tracked_task_done)

    try:
        accepted = await manager.enqueue({"text": "keep-me"}, user_id="owner")
        await asyncio.wait_for(first_write_failed.wait(), timeout=3)

        # While terminal write has not succeeded yet, queue item must remain unacknowledged.
        assert ack_calls == 0
        assert manager._queue._unfinished_tasks == 1

        allow_write_succeed.set()
        await asyncio.wait_for(manager._queue.join(), timeout=3)

        job = await manager.get_job(accepted["job_id"], "owner")
        assert job is not None
        assert job["status"] == "completed"
        assert job["result"] == {"echo": "keep-me", "run": 1}
        assert processor_calls == 1
        assert write_attempts >= 2
        assert ack_calls == 1
    finally:
        allow_write_succeed.set()
        await manager.stop()


@pytest.mark.asyncio
async def test_recover_jobs_restores_per_caller_counts_and_clears_on_dequeue():
    """Recovered queued jobs count toward their caller's bound until dequeued by a worker."""
    manager1 = AsyncQueryJobManager(max_queue_size=5, job_ttl_seconds=60, per_caller_queue_max=2)
    gate1 = asyncio.Event()

    async def blocking_processor(payload: dict, job_id: str, user_id: str) -> dict:
        await gate1.wait()
        return {"ok": True}

    manager1.register_processor(blocking_processor)
    await manager1.start(worker_count=1)

    try:
        first = await manager1.enqueue({"text": "in-flight"}, user_id="owner", caller="1.1.1.1")
        await _wait_for_status(manager1, first["job_id"], "processing")
        q1 = await manager1.enqueue({"text": "waiting-1"}, user_id="owner", caller="1.1.1.1")
        q2 = await manager1.enqueue({"text": "waiting-2"}, user_id="owner", caller="1.1.1.1")
    finally:
        await manager1.stop()
        gate1.set()

    # Restart with per_caller_queue_max=1: worker claims q1 and blocks, leaving q2
    # queued in _queue so caller 1.1.1.1 is already at its recovered bound of 1.
    manager2 = AsyncQueryJobManager(max_queue_size=5, job_ttl_seconds=60, per_caller_queue_max=1)
    gate2 = asyncio.Event()

    async def resumed_processor(payload: dict, job_id: str, user_id: str) -> dict:
        await gate2.wait()
        return {"echo": payload["text"]}

    manager2.register_processor(resumed_processor)
    await manager2.start(worker_count=1)
    try:
        await _wait_for_status(manager2, q1["job_id"], "processing")

        with pytest.raises(asyncio.QueueFull):
            await manager2.enqueue({"text": "blocked"}, user_id="owner", caller="1.1.1.1")
        other_caller = await manager2.enqueue({"text": "other"}, user_id="owner", caller="2.2.2.2")
        assert other_caller["status"] == "queued"

        gate2.set()
        await _wait_for_terminal_status(manager2, q2["job_id"])

        reopened = await manager2.enqueue({"text": "after-drain"}, user_id="owner", caller="1.1.1.1")
        assert reopened["status"] == "queued"
    finally:
        gate2.set()
        await manager2.stop()


@pytest.mark.asyncio
async def test_nonserializable_processor_result_fails_immediately_without_retry():
    """Circular or non-JSON-key processor output fails via the job-failure path instead of retrying forever."""
    manager = AsyncQueryJobManager(max_queue_size=5, job_ttl_seconds=60)

    async def bad_processor(payload: dict, job_id: str, user_id: str) -> dict:
        circular: dict = {"a": 1}
        circular["self"] = circular
        return circular

    manager.register_processor(bad_processor)
    await manager.start(worker_count=1)

    try:
        accepted = await manager.enqueue({"text": "circular"}, user_id="owner")
        await asyncio.wait_for(manager._queue.join(), timeout=3)

        job = await manager.get_job(accepted["job_id"], "owner")
        assert job is not None
        assert job["status"] == "failed"
        assert job["result"] is None
        assert job["error"] == "Internal error processing query"
        assert manager._retry_tasks == set()
    finally:
        await manager.stop()


@pytest.mark.asyncio
async def test_stop_cancels_retry_spawned_during_worker_unwind_and_isolates_replacement_queue(monkeypatch):
    """A retry task spawned while a cancelled worker unwinds is cancelled/awaited by stop()
    and cannot call task_done() on a replacement queue after configure() + start()."""
    manager = AsyncQueryJobManager(max_queue_size=5, job_ttl_seconds=60)
    in_processor = asyncio.Event()
    spawned_tasks: list[asyncio.Task] = []

    async def cleanup_failing_processor(payload: dict, job_id: str, user_id: str) -> dict:
        in_processor.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            raise RuntimeError("cleanup error during cancellation")

    real_finish = job_store.finish_job

    def fail_during_shutdown(*args, **kwargs):
        if manager._shutdown_event.is_set():
            raise RuntimeError("storage unavailable during shutdown")
        return real_finish(*args, **kwargs)

    real_retry = manager._retry_finish_job

    async def tracked_retry(*args, **kwargs):
        task = asyncio.current_task()
        if task is not None:
            spawned_tasks.append(task)
        return await real_retry(*args, **kwargs)

    monkeypatch.setattr(job_store, "finish_job", fail_during_shutdown)
    monkeypatch.setattr(manager, "_retry_finish_job", tracked_retry)

    manager.register_processor(cleanup_failing_processor)
    await manager.start(worker_count=1)

    await manager.enqueue({"text": "in-flight"}, user_id="owner")
    await asyncio.wait_for(in_processor.wait(), timeout=3)

    await manager.stop()
    assert manager._retry_tasks == set()
    assert all(t.done() for t in spawned_tasks)

    # Reconfigure (replaces _queue) and restart; nothing from the old run may touch the new queue.
    async def ok_processor(payload: dict, job_id: str, user_id: str) -> dict:
        return {"ok": True}

    await manager.configure(max_queue_size=5, job_ttl_seconds=60)
    replacement_queue = manager._queue
    manager.register_processor(ok_processor)
    await manager.start(worker_count=1)
    try:
        await asyncio.sleep(0.2)
        assert replacement_queue._unfinished_tasks == 0
        accepted = await manager.enqueue({"text": "fresh"}, user_id="owner")
        done = await _wait_for_terminal_status(manager, accepted["job_id"])
        assert done["status"] == "completed"
    finally:
        await manager.stop()
