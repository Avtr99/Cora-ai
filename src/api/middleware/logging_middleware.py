"""
Request/Response logging middleware with structured logging and request ID tracking.
Uses loguru for structured logging output.
"""
import asyncio
import logging
import time
import uuid
from typing import Callable, Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from starlette.responses import Response
from loguru import logger
import sys
from contextvars import ContextVar


class InterceptHandler(logging.Handler):
    """Intercept stdlib logging records and forward them to loguru.

    This ensures modules that still use the standard ``logging`` module have
    their output visible alongside the structured loguru logs.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Patch the loguru record with the original stdlib caller location so
        # the module/function/line in the output point to the actual source
        # file instead of the stdlib logging internals.
        def _patch(record_dict: dict) -> None:
            record_dict["module"] = record.module
            record_dict["function"] = record.funcName
            record_dict["line"] = record.lineno

        logger.patch(_patch).opt(exception=record.exc_info).log(
            level, record.getMessage()
        )

# Context variable for request ID (accessible throughout request lifecycle)
request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def get_request_id() -> Optional[str]:
    """Get current request ID from context."""
    return request_id_ctx.get()


def configure_logging(
    log_level: str = "INFO",
    json_logs: bool = False,
    log_file: Optional[str] = None
) -> None:
    """
    Configure loguru for structured logging.
    
    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: Output logs in JSON format (recommended for production)
        log_file: Optional file path for log output
    """
    # Remove default handler
    logger.remove()
    
    # Define log format
    if json_logs:
        # JSON format for production (easy parsing by log aggregators)
        log_format = (
            '{{"timestamp": "{time:YYYY-MM-DDTHH:mm:ss.SSSZ}", '
            '"level": "{level}", '
            '"request_id": "{extra[request_id]}", '
            '"message": "{message}", '
            '"module": "{module}", '
            '"function": "{function}", '
            '"line": {line}}}'
        )
    else:
        # Human-readable format for development
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{extra[request_id]}</cyan> | "
            "<cyan>{module}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )
    
    # Add console handler. Some deployment contexts (e.g., Windows background
    # processes without a real TTY) can make sys.stdout invalid for flushing;
    # fall back to stderr or a no-op sink so the server keeps running.
    try:
        logger.add(
            sys.stdout,
            format=log_format,
            level=log_level,
            colorize=not json_logs,
            serialize=False
        )
    except (OSError, ValueError):
        try:
            logger.add(
                sys.stderr,
                format=log_format,
                level=log_level,
                colorize=not json_logs,
                serialize=False
            )
        except (OSError, ValueError):
            # Last resort: no-op sink so loguru does not crash the process.
            logger.add(lambda _: None, format=log_format, level=log_level)

    # Add file handler if specified
    if log_file:
        try:
            logger.add(
                log_file,
                format=log_format,
                level=log_level,
                rotation="100 MB",
                retention="7 days",
                compression="gz"
            )
        except (OSError, ValueError) as exc:
            logger.warning(f"Could not add file log sink {log_file}: {exc}")
    
    # Bind default request_id
    logger.configure(extra={"request_id": "-"})

    # Route standard-library logging through loguru so the many stdlib loggers
    # in the codebase (agents, retrieval, etc.) are visible.
    root = logging.getLogger()
    root.handlers = [InterceptHandler()]
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for request/response logging with timing and request ID tracking.
    
    Features:
    - Generates unique request ID for each request
    - Logs request details (method, path, client)
    - Logs response details (status, duration)
    - Tracks performance metrics
    """
    
    REQUEST_ID_HEADER = "X-Request-ID"
    
    def __init__(
        self,
        app: ASGIApp,
        exclude_paths: Optional[list] = None,
        log_request_body: bool = False,
        log_response_body: bool = False
    ):
        """
        Initialize logging middleware.
        
        Args:
            app: ASGI application
            exclude_paths: Paths to exclude from logging (e.g., health checks)
            log_request_body: Whether to log request body (careful with sensitive data)
            log_response_body: Whether to log response body
        """
        super().__init__(app)
        self.exclude_paths = exclude_paths or ["/health", "/docs", "/redoc", "/openapi.json"]
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
    
    def _generate_request_id(self) -> str:
        """Generate unique request ID."""
        return str(uuid.uuid4())[:8]
    
    def _should_log(self, path: str) -> bool:
        """Check if request should be logged."""
        return not any(path == excluded or path.startswith(excluded + "/") for excluded in self.exclude_paths)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with logging."""
        # Get or generate request ID
        request_id = request.headers.get(self.REQUEST_ID_HEADER) or self._generate_request_id()
        
        # Set request ID in context
        token = request_id_ctx.set(request_id)
        
        # Bind request ID to logger
        with logger.contextualize(request_id=request_id):
            start_time = time.perf_counter()
            
            # Log request if not excluded
            if self._should_log(request.url.path):
                client_host = request.client.host if request.client else "unknown"
                logger.info(
                    f"Request started | {request.method} {request.url.path} | "
                    f"Client: {client_host}"
                )
            
            # Process request
            try:
                response = await call_next(request)
                
                # Calculate duration
                duration_ms = (time.perf_counter() - start_time) * 1000
                
                # Add request ID to response headers
                response.headers[self.REQUEST_ID_HEADER] = request_id
                response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
                
                # Log response if not excluded
                if self._should_log(request.url.path):
                    log_level = "INFO" if response.status_code < 400 else "WARNING"
                    if response.status_code >= 500:
                        log_level = "ERROR"
                    
                    logger.log(
                        log_level,
                        f"Request completed | {request.method} {request.url.path} | "
                        f"Status: {response.status_code} | Duration: {duration_ms:.2f}ms"
                    )
                
                return response
                
            except asyncio.CancelledError:
                if self._should_log(request.url.path):
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    logger.info(
                        f"Request cancelled | {request.method} {request.url.path} | "
                        f"Duration: {duration_ms:.2f}ms"
                    )
                raise
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.error(
                    f"Request failed | {request.method} {request.url.path} | "
                    f"Error: {str(e)} | Duration: {duration_ms:.2f}ms"
                )
                raise
            finally:
                # Reset context
                request_id_ctx.reset(token)


# Performance metrics storage (in-memory, consider Redis for production clustering)
class MetricsCollector:
    """Simple in-memory metrics collector for response times and cache hit rates."""
    
    def __init__(self, window_size: int = 1000):
        """
        Initialize metrics collector.
        
        Args:
            window_size: Number of recent requests to track
        """
        self.window_size = window_size
        self._response_times: list = []
        self._cache_hits: int = 0
        self._cache_misses: int = 0
        self._request_count: int = 0
        self._error_count: int = 0
    
    def record_response_time(self, duration_ms: float) -> None:
        """Record a response time."""
        self._response_times.append(duration_ms)
        if len(self._response_times) > self.window_size:
            self._response_times.pop(0)
        self._request_count += 1
    
    def record_cache_hit(self) -> None:
        """Record a cache hit."""
        self._cache_hits += 1
    
    def record_cache_miss(self) -> None:
        """Record a cache miss."""
        self._cache_misses += 1
    
    def record_error(self) -> None:
        """Record an error."""
        self._error_count += 1
    
    def get_metrics(self) -> dict:
        """Get current metrics summary."""
        if not self._response_times:
            return {
                "request_count": self._request_count,
                "error_count": self._error_count,
                "cache_hit_rate": 0.0,
                "response_time_p50": 0.0,
                "response_time_p95": 0.0,
                "response_time_p99": 0.0
            }
        
        sorted_times = sorted(self._response_times)
        n = len(sorted_times)
        
        total_cache = self._cache_hits + self._cache_misses
        cache_hit_rate = (self._cache_hits / total_cache * 100) if total_cache > 0 else 0.0
        
        return {
            "request_count": self._request_count,
            "error_count": self._error_count,
            "cache_hit_rate": round(cache_hit_rate, 2),
            "response_time_p50": round(sorted_times[int(n * 0.5)], 2),
            "response_time_p95": round(sorted_times[int(n * 0.95)], 2),
            "response_time_p99": round(sorted_times[min(int(n * 0.99), n - 1)], 2)
        }


# Global metrics instance
_metrics = MetricsCollector()


def get_metrics() -> dict:
    """Get current performance metrics."""
    return _metrics.get_metrics()


def record_response_time(duration_ms: float) -> None:
    """Record a response time."""
    _metrics.record_response_time(duration_ms)


def record_cache_hit() -> None:
    """Record a cache hit."""
    _metrics.record_cache_hit()


def record_cache_miss() -> None:
    """Record a cache miss."""
    _metrics.record_cache_miss()
