"""
Standardized error handling for the API.
Provides consistent error responses across all endpoints.
"""
from typing import Optional, Any, Dict
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel
from loguru import logger

from .logging_middleware import get_request_id

_ERROR_SLUGS = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    413: "payload_too_large",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    502: "bad_gateway",
    503: "service_unavailable",
    504: "gateway_timeout",
}


class ErrorResponse(BaseModel):
    """Standardized error response model."""
    error: str
    message: str
    request_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


def create_error_response(
    status_code: int,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> JSONResponse:
    """Create standardized error response."""
    request_id = get_request_id()

    content = {
        "error": _ERROR_SLUGS.get(status_code, "error"),
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


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTP exceptions."""
    return create_error_response(
        status_code=exc.status_code,
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
        message="Request validation failed",
        details={"validation_errors": field_errors}
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    logger.exception(f"Unhandled exception: {str(exc)}")

    return create_error_response(
        status_code=500,
        message="An internal server error occurred"
    )


def register_exception_handlers(app) -> None:
    """Register all exception handlers with the FastAPI app."""
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
