"""API middleware modules."""
from .security import (
    SecurityMiddleware,
    generate_api_key,
    AuthenticatedUser,
    get_authenticated_user,
    validate_user_access
)
from .input_sanitizer import (
    InputSanitizer,
    OutputSanitizer,
    SanitizationResult,
    ThreatLevel,
    get_input_sanitizer,
    get_output_sanitizer
)
from .logging_middleware import (
    LoggingMiddleware,
    configure_logging,
    get_request_id,
    get_metrics,
    record_cache_hit,
    record_cache_miss,
    record_response_time
)
from .circuit_breaker import (
    CircuitBreaker,
    CircuitConfig,
    CircuitOpenError,
    get_circuit_breaker,
    get_all_circuit_stats,
    gemini_circuit,
    voyage_circuit,
    qdrant_circuit
)
from .error_handler import (
    APIError,
    ErrorCode,
    ErrorResponse,
    register_exception_handlers
)
from .request_size_limit import RequestSizeLimitMiddleware

__all__ = [
    # Security
    "SecurityMiddleware",
    "generate_api_key",
    "AuthenticatedUser",
    "get_authenticated_user",
    "validate_user_access",
    # Input/Output Sanitization
    "InputSanitizer",
    "OutputSanitizer",
    "SanitizationResult",
    "ThreatLevel",
    "get_input_sanitizer",
    "get_output_sanitizer",
    # Logging
    "LoggingMiddleware",
    "configure_logging",
    "get_request_id",
    "get_metrics",
    "record_cache_hit",
    "record_cache_miss",
    "record_response_time",
    # Circuit breaker
    "CircuitBreaker",
    "CircuitConfig",
    "CircuitOpenError",
    "get_circuit_breaker",
    "get_all_circuit_stats",
    "gemini_circuit",
    "voyage_circuit",
    "qdrant_circuit",
    # Error handling
    "APIError",
    "ErrorCode",
    "ErrorResponse",
    "register_exception_handlers",
    # Request size limits
    "RequestSizeLimitMiddleware",
]
