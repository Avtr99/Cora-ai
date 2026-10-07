"""Login-attempt rate limiting.

One in-memory ``limits`` moving-window limiter, keyed on ``(scope, key)`` —
``ip:username`` for logins, the user ID for password changes. Five
attempts per minute, every attempt counts. A single uvicorn process serves
HTTP, so memory state is correct; counters reset on restart.
"""

from fastapi import HTTPException
from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

LOGIN_LIMIT = parse("5/minute")

_limiter = MovingWindowRateLimiter(MemoryStorage())


def require_attempt(scope: str, key: str) -> None:
    """Count this attempt; 429 when the limit is already hit."""
    if not _limiter.hit(LOGIN_LIMIT, scope, key):
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Try again in a minute.",
            headers={"Retry-After": "60"},
        )


def reset() -> None:
    """Clear all counters. Test-only helper — never called at runtime."""
    _limiter.storage.reset()
