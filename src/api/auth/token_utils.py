"""
JWT token utilities for authentication.

Provides functions for creating and validating JWT access tokens.
"""
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from loguru import logger

from ...config import get_settings

PROTECTED_CLAIMS = {"sub", "exp", "iat", "nbf", "jti", "type", "aud", "iss"}
ALLOWED_CLAIM_VALUE_TYPES = (str, int, float, bool)


class JWTError(Exception):
    """Custom exception for JWT-related errors."""
    
    def __init__(self, message: str, error_code: str = "JWT_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


def _normalize_user_id(user_id: Any) -> str:
    """Validate and normalize user_id input."""
    if not isinstance(user_id, str):
        raise ValueError("user_id must be a string")
    normalized = user_id.strip()
    if not normalized:
        raise ValueError("user_id cannot be empty")
    if len(normalized) > 256:
        raise ValueError("user_id exceeds maximum length of 256 characters")
    return normalized


def _sanitize_additional_claims(additional_claims: Dict[str, Any]) -> Dict[str, Any]:
    """Remove protected claims and validate custom claim values."""
    sanitized = {}
    for key, value in additional_claims.items():
        if key in PROTECTED_CLAIMS:
            logger.warning(f"Ignoring attempt to override protected JWT claim: {key}")
            continue
        if value is not None and not isinstance(value, ALLOWED_CLAIM_VALUE_TYPES):
            raise JWTError(
                f"Claim '{key}' must be a primitive JSON value",
                "JWT_INVALID_CLAIM"
            )
        sanitized[key] = value
    return sanitized


def create_access_token(
    user_id: str,
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[dict] = None
) -> str:
    """
    Create a JWT access token for a user.
    
    Args:
        user_id: The user identifier to encode in the token
        expires_delta: Optional custom expiration time. Defaults to settings value.
        additional_claims: Optional additional claims to include in the token
        
    Returns:
        Encoded JWT token string
        
    Raises:
        JWTError: If token creation fails
    """
    try:
        normalized_user_id = _normalize_user_id(user_id)
    except ValueError as exc:
        raise JWTError(str(exc), "JWT_INVALID_INPUT") from exc
    
    settings = get_settings()
    
    if not settings.JWT_SECRET_KEY:
        raise JWTError("JWT_SECRET_KEY environment variable is required but not set", "JWT_CONFIG_ERROR")
    
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    issued_at = datetime.now(timezone.utc)
    expire = issued_at + expires_delta
    
    payload = {
        "sub": normalized_user_id,  # Subject (user identifier)
        "exp": expire,   # Expiration time
        "iat": issued_at,  # Issued at
        "type": "access"  # Token type
    }
    
    if additional_claims:
        sanitized_claims = _sanitize_additional_claims(additional_claims)
        payload.update(sanitized_claims)
    
    try:
        encoded_jwt = jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        anonymized_id = hashlib.sha256(normalized_user_id.encode("utf-8")).hexdigest()[:8]
        logger.debug(f"Created access token for user hash: {anonymized_id}")
        return encoded_jwt
    except Exception as e:
        logger.error("Failed to create access token", exc_info=False)
        raise JWTError("Failed to create token", "JWT_CREATE_ERROR") from e


def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT access token.
    
    Args:
        token: The JWT token string to decode
        
    Returns:
        Dictionary containing the token payload with user_id
        
    Raises:
        JWTError: If token is invalid, expired, or malformed
    """
    settings = get_settings()
    
    if not settings.JWT_SECRET_KEY:
        raise JWTError("JWT_SECRET_KEY environment variable is required but not set", "JWT_CONFIG_ERROR")
    
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        user_id = payload.get("sub")
        if not user_id:
            raise JWTError("Token missing user identifier", "JWT_INVALID_PAYLOAD")
        
        token_type = payload.get("type")
        if token_type != "access":
            raise JWTError("Invalid token type", "JWT_INVALID_TYPE")
        
        return {
            "user_id": user_id,
            "exp": payload.get("exp"),
            "iat": payload.get("iat"),
            **{k: v for k, v in payload.items() if k not in ("sub", "exp", "iat", "type")}
        }
        
    except jwt.ExpiredSignatureError:
        logger.warning("Attempted to use expired token")
        raise JWTError("Token has expired", "JWT_EXPIRED")
    except jwt.InvalidTokenError:
        logger.warning("Invalid token detected")
        raise JWTError("Invalid token", "JWT_INVALID")
    except JWTError:
        raise
    except Exception:
        logger.error("Unexpected error decoding token", exc_info=False)
        raise JWTError("Token validation failed", "JWT_DECODE_ERROR")
