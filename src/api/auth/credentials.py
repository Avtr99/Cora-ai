"""Credential types and password hashing for user accounts.

``Username`` and ``Password`` are the request-boundary types: usernames
are lowercased and restricted to ``^[a-z0-9][a-z0-9._-]{2,31}$``; passwords are
15-128 characters with no composition rules (NIST SP 800-63B-4). Hashing
uses pwdlib's argon2 backend.
"""
import asyncio
import threading
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated

from fastapi import HTTPException
from pwdlib import PasswordHash
from pydantic import AfterValidator, BeforeValidator, StringConstraints


def _normalize_username(value: object) -> object:
    # pydantic checks ``pattern`` on the raw input, before StringConstraints
    # can strip/lower it — normalize first so "  Alice " validates as "alice".
    return value.strip().lower() if isinstance(value, str) else value


def _reject_repeated_char(value: str) -> str:
    if len(set(value)) == 1:
        raise ValueError("Password must not be one repeated character.")
    return value


Username = Annotated[
    str,
    BeforeValidator(_normalize_username),
    StringConstraints(pattern=r"^[a-z0-9][a-z0-9._-]{2,31}$"),
]
Password = Annotated[
    str,
    StringConstraints(min_length=15, max_length=128),
    AfterValidator(_reject_repeated_char),
]

_password_hasher = PasswordHash.recommended()
_DUMMY_HASH = _password_hasher.hash("dummy-password-for-timing")

_HASH_WORKERS = 2          # bounds argon2 CPU/RAM (64 MiB each)
_HASH_QUEUE_LIMIT = 16     # requests allowed to wait; the rest get 503 at once
_hash_executor = ThreadPoolExecutor(
    max_workers=_HASH_WORKERS, thread_name_prefix="argon2"
)
# threading, not asyncio: an asyncio.Semaphore binds to one event loop, and
# each TestClient spins up its own.
_hash_slots = threading.BoundedSemaphore(_HASH_QUEUE_LIMIT)


def _normalize_password(password: str) -> str:
    # Compatibility characters hash to their canonical bytes, so a password
    # verifies identically however the input encoded it.
    return unicodedata.normalize("NFKC", password)


def hash_password(password: str) -> str:
    """Hash ``password`` with the recommended argon2 parameters."""
    return _password_hasher.hash(_normalize_password(password))


def verify_password(password: str, password_hash: str | None) -> bool:
    """Return True when ``password`` matches ``password_hash``.

    ``password_hash=None`` (unknown user or unclaimed owner) still runs a real
    verify against a dummy hash so response time does not reveal which
    accounts exist; it always returns False.
    """
    password = _normalize_password(password)
    if password_hash is None:
        _password_hasher.verify(password, _DUMMY_HASH)
        return False
    return _password_hasher.verify(password, password_hash)


async def _run_hasher(fn, *args):
    """Run ``fn`` on the argon2 executor; 503 when the queue is full.

    argon2 is CPU- and RAM-heavy (~64 MiB per op), and the default
    ``asyncio.to_thread`` pool also serves session lookups — an unbounded
    login flood would starve every request. Two workers and a bounded wait
    queue keep hashing isolated; overflow fails fast instead of queueing.
    """
    if not _hash_slots.acquire(blocking=False):
        raise HTTPException(
            status_code=503,
            detail="Sign-in is busy. Try again in a few seconds.",
            headers={"Retry-After": "5"},
        )
    try:
        future = _hash_executor.submit(fn, *args)
    except Exception:
        _hash_slots.release()
        raise
    # The slot is released when the executor work finishes, not when this await
    # ends — a cancelled request still leaves argon2 running in the thread.
    future.add_done_callback(lambda _: _hash_slots.release())
    return await asyncio.wrap_future(future)


async def hash_password_async(password: str) -> str:
    """``hash_password`` on the bounded argon2 executor."""
    return await _run_hasher(hash_password, password)


async def verify_password_async(password: str, password_hash: str | None) -> bool:
    """``verify_password`` on the bounded argon2 executor."""
    return await _run_hasher(verify_password, password, password_hash)
