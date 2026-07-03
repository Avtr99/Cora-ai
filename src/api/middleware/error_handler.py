"""
Standardized error handling with error codes for the API.
Provides consistent error responses across all endpoints.
"""
from enum import Enum
from typing import Optional, Any, Dict
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel
from loguru import logger

from .logging_middleware import get_request_id


class ErrorCode(str, Enum):
    """Standardized error codes for API responses."""
    # Authentication errors (1xx)
    AUTH_001 = "AUTH_001"  # Invalid or missing API key
    AUTH_002 = "AUTH_002"  # Token expired
    AUTH_003 = "AUTH_003"  # Insufficient permissions
    
    # Rate limiting errors (2xx)
    RATE_001 = "RATE_001"  # Rate limit exceeded
    RATE_002 = "RATE_002"  # Burst limit exceeded
    
    # Validation errors (3xx)
    VAL_001 = "VAL_001"   # Invalid request body
    VAL_002 = "VAL_002"   # Missing required field
    VAL_003 = "VAL_003"   # Invalid field value
    VAL_004 = "VAL_004"   # Query too long
    VAL_005 = "VAL_005"   # Invalid document format
    
    # Resource errors (4xx)
    RES_001 = "RES_001"   # Resource not found
    RES_002 = "RES_002"   # Resource already exists
    RES_003 = "RES_003"   # Resource conflict
    
    # External service errors (5xx)
    EXT_001 = "EXT_001"   # Gemini API error
    EXT_002 = "EXT_002"   # Voyage API error
    EXT_003 = "EXT_003"   # Qdrant error
    EXT_004 = "EXT_004"   # Firestore error
    EXT_005 = "EXT_005"   # External service timeout
    EXT_006 = "EXT_006"   # Circuit breaker open
    
    # Internal errors (9xx)
    INT_001 = "INT_001"   # Internal server error
    INT_002 = "INT_002"   # Configuration error
    INT_003 = "INT_003"   # Cache error


class ErrorResponse(BaseModel):
    """Standardized error response model."""
    error: str
    error_code: str
    message: str
    request_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class APIError(Exception):
    """
    Custom API exception with error code support.
    
    Usage:
        raise APIError(
            status_code=400,
            error_code=ErrorCode.VAL_001,
            message="Invalid request body",
            details={"field": "text", "issue": "cannot be empty"}
        )
    """
    
    def __init__(
        self,
        status_code: int,
        error_code: ErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.details = details
        super().__init__(message)


def create_error_response(
    status_code: int,
    error_code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> JSONResponse:
    """Create standardized error response."""
    request_id = get_request_id()
    
    content = {
        "error": error_code.split("_")[0].lower() if "_" in error_code else "error",
        "error_code": error_code,
        "message": message
    }
    
    if request_id:
        content["request_id"] = request_id
    
    if details:
        content["details"] = details
    
    return JSONResponse(
        status_code=status_code,
        content=content
    )


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle custom API errors."""
    logger.error(f"API Error: {exc.error_code.value} - {exc.message}")
    
    return create_error_response(
        status_code=exc.status_code,
        error_code=exc.error_code.value,
        message=exc.message,
        details=exc.details
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTP exceptions."""
    # Map HTTP status codes to error codes
    error_code_map = {
        400: ErrorCode.VAL_001.value,
        401: ErrorCode.AUTH_001.value,
        403: ErrorCode.AUTH_003.value,
        404: ErrorCode.RES_001.value,
        409: ErrorCode.RES_003.value,
        429: ErrorCode.RATE_001.value,
        500: ErrorCode.INT_001.value,
        502: ErrorCode.EXT_001.value,
        503: ErrorCode.EXT_006.value,
        504: ErrorCode.EXT_005.value
    }
    
    error_code = error_code_map.get(exc.status_code, ErrorCode.INT_001.value)
    
    return create_error_response(
        status_code=exc.status_code,
        error_code=error_code,
        message=str(exc.detail)
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic validation errors."""
    errors = exc.errors()
    
    # Extract field-level errors
    field_errors = {}
    for error in errors:
        loc = ".".join(str(part) for part in error["loc"] if part != "body")
        field_errors[loc] = error["msg"]
    
    logger.warning(f"Validation error: {field_errors}")
    
    return create_error_response(
        status_code=422,
        error_code=ErrorCode.VAL_001.value,
        message="Request validation failed",
        details={"validation_errors": field_errors}
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    logger.exception(f"Unhandled exception: {str(exc)}")
    
    return create_error_response(
        status_code=500,
        error_code=ErrorCode.INT_001.value,
        message="An internal server error occurred"
    )


def register_exception_handlers(app) -> None:
    """Register all exception handlers with the FastAPI app."""
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
