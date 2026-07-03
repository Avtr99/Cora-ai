"""
Circuit breaker pattern implementation for external API calls.
Prevents cascading failures when external services are unavailable.
"""
import time
import asyncio
import threading
from enum import Enum
from typing import Callable, Optional, TypeVar
from functools import wraps
from dataclasses import dataclass
from loguru import logger

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation, requests flow through
    OPEN = "open"          # Circuit tripped, requests fail fast
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitStats:
    """Statistics for a circuit breaker."""
    failures: int = 0
    successes: int = 0
    last_failure_time: float = 0.0
    last_success_time: float = 0.0
    consecutive_failures: int = 0
    consecutive_successes: int = 0


@dataclass
class CircuitConfig:
    """Configuration for circuit breaker behavior."""
    failure_threshold: int = 5          # Failures before opening circuit
    success_threshold: int = 3          # Successes in half-open to close
    timeout_seconds: float = 30.0       # Time before half-open attempt
    half_open_max_calls: int = 3        # Max calls in half-open state


class CircuitBreaker:
    """
    Circuit breaker for external service calls.
    
    States:
    - CLOSED: Normal operation, all calls go through
    - OPEN: Service is down, calls fail immediately
    - HALF_OPEN: Testing if service recovered
    
    Usage:
        breaker = CircuitBreaker("gemini_api")
        
        @breaker
        async def call_gemini(...):
            ...
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[CircuitConfig] = None,
        fallback: Optional[Callable] = None
    ):
        """
        Initialize circuit breaker.
        
        Args:
            name: Identifier for this circuit
            config: Circuit breaker configuration
            fallback: Optional fallback function when circuit is open
        """
        self.name = name
        self.config = config or CircuitConfig()
        self.fallback = fallback
        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
        # ponytail: regular lock is fine for fast state transitions; keeps the
        # async lock for the async HALF_OPEN call counting.
        self._state_lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, transitioning if timeout expired."""
        with self._state_lock:
            if self._state == CircuitState.OPEN:
                time_since_failure = time.time() - self._stats.last_failure_time
                if time_since_failure >= self.config.timeout_seconds:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info(f"Circuit '{self.name}' transitioning to HALF_OPEN")
            return self._state

    def _record_success(self) -> None:
        """Record successful call."""
        with self._state_lock:
            self._stats.successes += 1
            self._stats.last_success_time = time.time()
            self._stats.consecutive_failures = 0
            self._stats.consecutive_successes += 1

            if self._state == CircuitState.HALF_OPEN:
                if self._stats.consecutive_successes >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._stats.consecutive_successes = 0
                    logger.info(f"Circuit '{self.name}' CLOSED after recovery")

    def _record_failure(self, error: Exception) -> None:
        """Record failed call."""
        with self._state_lock:
            self._stats.failures += 1
            self._stats.last_failure_time = time.time()
            self._stats.consecutive_successes = 0
            self._stats.consecutive_failures += 1

            logger.warning(f"Circuit '{self.name}' failure: {str(error)}")

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(f"Circuit '{self.name}' OPEN after half-open failure")
            elif self._stats.consecutive_failures >= self.config.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(f"Circuit '{self.name}' OPEN after {self._stats.consecutive_failures} failures")

    async def _can_execute(self) -> bool:
        """Check if call can be executed based on circuit state."""
        current_state = self.state

        if current_state == CircuitState.CLOSED:
            return True

        if current_state == CircuitState.OPEN:
            return False

        # HALF_OPEN: allow limited calls
        async with self._lock:
            if self._half_open_calls < self.config.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False
    
    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function through circuit breaker.

        Args:
            func: Async function to call
            *args, **kwargs: Arguments for function

        Returns:
            Function result

        Raises:
            CircuitOpenError: If circuit is open and no fallback
            Original exception: If call fails and no fallback
        """
        if not await self.can_execute():
            if self.fallback:
                logger.debug(f"Circuit '{self.name}' open, using fallback")
                return await self.fallback(*args, **kwargs) if asyncio.iscoroutinefunction(self.fallback) else self.fallback(*args, **kwargs)
            raise CircuitOpenError(f"Circuit '{self.name}' is open")

        try:
            # NOTE: `await X if C else Y` is parsed as `(await X) if C else Y`,
            # so the await does NOT apply to the `else` branch. Use a normal if/else
            # to ensure both sync and async callables are awaited correctly.
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    result = await result
            self.record_success()
            return result
        except Exception as e:
            self.record_failure(e)
            if self.fallback:
                if asyncio.iscoroutinefunction(self.fallback):
                    return await self.fallback(*args, **kwargs)
                else:
                    return self.fallback(*args, **kwargs)
            raise

    async def can_execute(self) -> bool:
        """Check if a call can be executed based on circuit state.

        Public alias for ``_can_execute`` so callers (e.g. streaming code
        that cannot use ``call`` because it wraps an async generator) can
        inspect the circuit without relying on private internals.
        """
        return await self._can_execute()

    def record_success(self) -> None:
        """Record a successful call. Public alias for ``_record_success``."""
        self._record_success()

    def record_failure(self, error: Exception) -> None:
        """Record a failed call. Public alias for ``_record_failure``."""
        self._record_failure(error)
    
    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator for circuit breaker."""
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await self.call(func, *args, **kwargs)
        return wrapper
    
    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failures": self._stats.failures,
            "successes": self._stats.successes,
            "consecutive_failures": self._stats.consecutive_failures,
            "last_failure_time": self._stats.last_failure_time,
            "last_success_time": self._stats.last_success_time
        }
    
    def reset(self) -> None:
        """Manually reset circuit to closed state."""
        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._half_open_calls = 0
        logger.info(f"Circuit '{self.name}' manually reset")


class CircuitOpenError(Exception):
    """Raised when circuit is open and call cannot proceed."""
    pass


# Global circuit breaker registry
_circuits: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    config: Optional[CircuitConfig] = None,
    fallback: Optional[Callable] = None
) -> CircuitBreaker:
    """
    Get or create a circuit breaker by name.
    
    Args:
        name: Circuit identifier
        config: Optional configuration
        fallback: Optional fallback function
        
    Returns:
        CircuitBreaker instance
    """
    if name not in _circuits:
        _circuits[name] = CircuitBreaker(name, config, fallback)
    return _circuits[name]


def get_all_circuit_stats() -> dict:
    """Get stats for all circuit breakers."""
    return {name: breaker.get_stats() for name, breaker in _circuits.items()}


# Pre-configured circuit breakers for external APIs
gemini_circuit = get_circuit_breaker(
    "gemini_api",
    CircuitConfig(
        failure_threshold=3,
        timeout_seconds=60.0,
        success_threshold=2
    )
)

voyage_circuit = get_circuit_breaker(
    "voyage_api",
    CircuitConfig(
        failure_threshold=3,
        timeout_seconds=60.0,
        success_threshold=2
    )
)

qdrant_circuit = get_circuit_breaker(
    "qdrant_db",
    CircuitConfig(
        failure_threshold=5,
        timeout_seconds=30.0,
        success_threshold=3
    )
)
