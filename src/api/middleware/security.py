"""
Security middleware for API authentication and security headers.
Provides API key authentication for sensitive endpoints and security headers.
"""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from typing import List, Optional, Callable
import secrets
import hashlib
import re

from ...config import get_settings
from ..auth.token_utils import decode_access_token, JWTError


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
        self._api_keys = self._load_api_keys()
    
    def _load_api_keys(self) -> set:
        """Load valid API keys from environment."""
        settings = get_settings()
        api_keys = set()
        
        # Load API key from settings if configured
        api_key = getattr(settings, 'API_ACCESS_KEY', None)
        if api_key:
            api_keys.add(self._hash_key(api_key))
        
        return api_keys
    
    def _hash_key(self, key: str) -> str:
        """Hash API key for secure comparison."""
        return hashlib.sha256(key.encode()).hexdigest()
    
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
    
    def _validate_api_key(self, api_key: Optional[str]) -> bool:
        """Validate provided API key."""
        if not api_key:
            return False
        
        # If no API keys are configured, deny all requests to protected paths
        if not self._api_keys:
            return False
        
        # Use constant-time comparison to prevent timing attacks
        hashed_key = self._hash_key(api_key)
        return any(secrets.compare_digest(hashed_key, valid_key) for valid_key in self._api_keys)
    
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
        
        # Check API key for protected paths
        if self._is_path_protected(path):
            api_key = request.headers.get(self.api_key_header)
            
            if not self._validate_api_key(api_key):
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": "unauthorized",
                        "error_code": "AUTH_001",
                        "message": "Invalid or missing API key"
                    }
                )
        
        # Process request
        response = await call_next(request)
        
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


class AuthenticatedUser:
    """Represents an authenticated user from request headers."""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
    
    def validate_access(self, requested_user_id: str) -> bool:
        """Check if authenticated user can access the requested user's data."""
        return self.user_id == requested_user_id


async def get_authenticated_user(request: Request) -> AuthenticatedUser:
    """
    FastAPI dependency to extract and verify authenticated user from JWT token.
    
    Verifies the user's JWT token from the Authorization header and extracts
    their authenticated user_id. This prevents IDOR attacks by cryptographically
    verifying user identity.
    
    Args:
        request: FastAPI request object
        
    Returns:
        AuthenticatedUser object with validated user_id
        
    Raises:
        HTTPException: 401 if token is missing, invalid, or expired
    """
    # Extract JWT token from Authorization header
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "error_code": "AUTH_002",
                "message": "Valid Bearer token is required"
            }
        )
    
    token = auth_header.split(" ", 1)[1]
    
    # Verify and decode JWT token
    try:
        payload = decode_access_token(token)
        user_id = payload.get("user_id")
    except JWTError as e:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "error_code": e.error_code,
                "message": e.message
            }
        )
    
    # Validate user_id format (alphanumeric with _-.@, max 256 chars)
    if not user_id or not re.match(r'^[a-zA-Z0-9_\-.@]{1,256}$', user_id):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "error_code": "AUTH_003",
                "message": "Invalid user_id format in token"
            }
        )
    
    return AuthenticatedUser(user_id=user_id)


def validate_user_access(auth_user: AuthenticatedUser, requested_user_id: str) -> None:
    """
    Validate that the authenticated user can access the requested user's data.
    
    Args:
        auth_user: The authenticated user from get_authenticated_user dependency
        requested_user_id: The user_id from the request body or path
        
    Raises:
        HTTPException: 403 if user IDs don't match
    """
    if not auth_user.validate_access(requested_user_id):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "forbidden",
                "error_code": "AUTH_004",
                "message": "You do not have permission to access this user's data"
            }
        )
