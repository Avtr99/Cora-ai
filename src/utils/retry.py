"""
Retry utilities - thin wrapper around tenacity library.

This module re-exports tenacity components for backward compatibility.
The project uses tenacity (already in requirements.txt) for robust,
battle-tested retry functionality.

Migration: Replace imports from this module with direct tenacity imports:
  from tenacity import retry, stop_after_attempt, wait_exponential

For new code, use tenacity directly instead of this wrapper.
"""

# Re-export tenacity components for backward compatibility
from tenacity import (
    retry,
    retry_if_exception_type,
    retry_if_exception,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential,
    wait_exponential_jitter,
    wait_fixed,
    before_sleep_log,
    RetryError as TenacityRetryError,
)

# Keep RetryError for backward compatibility
class RetryError(Exception):
    """Raised when all retry attempts have been exhausted."""
    
    def __init__(self, message: str, last_exception=None):
        super().__init__(message)
        self.last_exception = last_exception


# Convenience re-exports matching the old API
retry_sync = retry
retry_async = retry

__all__ = [
    "retry",
    "retry_sync",
    "retry_async",
    "retry_if_exception_type",
    "retry_if_exception",
    "stop_after_attempt",
    "stop_after_delay",
    "wait_exponential",
    "wait_exponential_jitter",
    "wait_fixed",
    "before_sleep_log",
    "RetryError",
    "TenacityRetryError",
]

