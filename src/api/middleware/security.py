"""
Security middleware for API authentication and security headers.
Provides API key authentication for sensitive endpoints and security headers.
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from typing import List, Optional, Callable
import asyncio
import secrets

from ...db.users import OWNER_USER_ID
from ..auth.session_auth import (
    SESSION_COOKIE,
    is_cross_site_request,
    key_matches,
    session_user_id,
)


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds security headers and optionally validates API keys.
    
    Security headers added:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - Strict-Transport-Security: max-age=31536000; includeSubDomains
    - Content-Security-Policy: default-src 'self'
    - Referrer-Policy: strict-origin-when-cross-origin
    """
    
    def __init__(
        self,
        app: ASGIApp,
        api_key_header: str = "X-API-Key",
        protected_paths: Optional[List[str]] = None,
        exclude_paths: Optional[List[str]] = None
    ):
        """
        Initialize security middleware.
        
        Args:
            app: ASGI application
            api_key_header: Header name for API key
            protected_paths: Paths that require API key (None = all paths)
            exclude_paths: Paths excluded from API key requirement
        """
        super().__init__(app)
        self.api_key_header = api_key_header
        self.protected_paths = protected_paths
        self.exclude_paths = exclude_paths or [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/rate-limit-info"
        ]

    def _is_path_protected(self, path: str) -> bool:
        """Check if path requires API key authentication."""
        # Check exclusions first (exact match or prefix-with-slash-boundary)
        for excluded in self.exclude_paths:
            if path == excluded or path.startswith(excluded + "/"):
                return False
        
        # If protected_paths is None, no paths are protected by default
        # This allows the system to work without API keys initially
        if self.protected_paths is None:
            return False
        
        # Check if path is in protected list (exact match or prefix-with-slash-boundary)
        for protected in self.protected_paths:
            if path == protected or path.startswith(protected + "/"):
                return True
        
        return False
    
    def _add_security_headers(self, response) -> None:
        """Add security headers to response."""
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "script-src 'self'; "
            "img-src 'self' data: https:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    
    async def dispatch(self, request: Request, call_next: Callable):
        """Process request through security middleware."""
        path = request.url.path
        
        # Check credentials for protected paths: X-API-Key header or session cookie
        if self._is_path_protected(path):
            api_key = request.headers.get(self.api_key_header)

            if key_matches(api_key):
                request.state.user_id = OWNER_USER_ID
            else:
                user_id = await asyncio.to_thread(
                    session_user_id, request.cookies.get(SESSION_COOKIE)
                )
                if user_id is not None:
                    if is_cross_site_request(request):
                        response = JSONResponse(
                            status_code=403,
                            content={
                                "error": "forbidden",
                                "message": "Cross-origin request rejected"
                            }
                        )
                        self._add_security_headers(response)
                        return response
                    request.state.user_id = user_id
                else:
                    response = JSONResponse(
                        status_code=401,
                        content={
                            "error": "unauthorized",
                            "message": "Invalid or missing API key"
                        }
                    )
                    self._add_security_headers(response)
                    return response

        # Process request
        response = await call_next(request)

        # Auth responses carry session state — never let a proxy cache them.
        if path.startswith(("/api/auth", "/v1/auth", "/api/account", "/v1/account")):
            response.headers["Cache-Control"] = "no-store"

        # Add security headers to all responses
        self._add_security_headers(response)
        
        return response


def generate_api_key() -> str:
    """
    Generate a secure API key for client authentication.
    
    Returns:
        A 64-character hexadecimal API key (32 bytes)
    """
    return secrets.token_hex(32)
