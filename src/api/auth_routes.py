"""
Authentication endpoints for JWT token issuance.

For development/testing purposes. In production, integrate with your actual
authentication system (OAuth, OIDC, etc.).
"""
import hashlib

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from loguru import logger

from .auth.token_utils import create_access_token
from .middleware.security import get_authenticated_user, AuthenticatedUser
from ..config import get_settings


router = APIRouter(prefix="/auth", tags=["Authentication"])


class TokenRequest(BaseModel):
    user_id: str = Field(..., description="User identifier to create token for")


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")


@router.post("/token", response_model=TokenResponse)
async def get_token(request: TokenRequest):
    """
    Issue a JWT access token for a user.
    
    **Development/Testing Only**: In production, this should be protected
    by your actual authentication system (password, OAuth, etc.).
    
    Example:
    ```bash
    curl -X POST http://localhost:8000/auth/token \
      -H "Content-Type: application/json" \
      -d '{"user_id": "user123"}'
    ```
    
    Response:
    ```json
    {
      "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "token_type": "bearer",
      "expires_in": 3600
    }
    ```
    
    Then use the token in protected endpoints:
    ```bash
    curl http://localhost:8000/memory/all/user123 \
      -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    ```
    """
    settings = get_settings()
    if not settings.ENABLE_INSECURE_TOKEN_ENDPOINT:
        raise HTTPException(status_code=404, detail="Endpoint not available")
    
    try:
        # Create JWT token for the user
        token = create_access_token(user_id=request.user_id)
        # Use a safe anonymization that doesn't expose secret key absence
        anonymized_id = hashlib.sha256(
            request.user_id.encode("utf-8")
        ).hexdigest()[:8]
        logger.info(f"Issued token for user hash: {anonymized_id}")
        
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    except Exception:
        logger.exception("Failed to create token")
        raise HTTPException(status_code=500, detail="Internal server error while creating token")


@router.get("/verify")
async def verify_token_endpoint(
    auth_user: AuthenticatedUser = Depends(get_authenticated_user),
):
    """
    Verify that JWT authentication is working.

    This endpoint requires a valid JWT token in the Authorization header.
    Use it to test that your token is valid.

    Example:
    ```bash
    curl http://localhost:8000/auth/verify \
      -H "Authorization: Bearer YOUR_TOKEN_HERE"
    ```
    """
    return {
        "status": "authenticated",
        "user_id": auth_user.user_id,
        "message": "Token is valid",
    }
