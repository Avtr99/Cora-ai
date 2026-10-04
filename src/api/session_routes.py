"""Browser session login endpoints for API-key-protected deployments.

When ``ENABLE_API_KEY_PROTECTION`` is on, a browser posts the instance access
key once and receives an HttpOnly session cookie (``cora_session``) backed by
a row in the ``auth_sessions`` table. Scripts keep using ``X-API-Key``. These
routes are mounted under ``/api`` and excluded from API-key enforcement in
``SecurityMiddleware``.
"""
import asyncio

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .auth.session_auth import (
    OWNER_USER_ID,
    SESSION_COOKIE,
    SESSION_TTL,
    create_session,
    delete_session,
    is_cross_site_request,
    key_matches,
    session_user_id,
)
from ..config import get_settings

router = APIRouter(prefix="/auth", tags=["Session"])


class LoginRequest(BaseModel):
    api_key: str = Field(min_length=1, max_length=512)


@router.get("/session")
async def get_session(request: Request):
    """Report whether login is required and whether the caller is authenticated.

    Never returns 401 — the SPA calls this to decide whether to show the login
    page. A valid ``X-API-Key`` header or session cookie counts as
    authenticated.
    """
    settings = get_settings()
    required = settings.ENABLE_API_KEY_PROTECTION
    authenticated = not required or key_matches(request.headers.get("X-API-Key"))
    if not authenticated:
        session_uid = await asyncio.to_thread(
            session_user_id, request.cookies.get(SESSION_COOKIE)
        )
        authenticated = session_uid is not None
    return {"required": required, "authenticated": authenticated}


@router.post("/session", status_code=204)
async def login(body: LoginRequest, request: Request, response: Response):
    """Exchange the instance access key for a session cookie."""
    settings = get_settings()
    if not settings.ENABLE_API_KEY_PROTECTION:
        raise HTTPException(status_code=404, detail="Endpoint not available")
    # The route is auth-excluded, so the middleware's CSRF guard never runs
    # here — without this, a cross-site POST could plant a session cookie in
    # a victim's browser (login CSRF).
    if is_cross_site_request(request):
        raise HTTPException(status_code=403, detail="Cross-origin request rejected")
    if not key_matches(body.api_key):
        raise HTTPException(status_code=401, detail="Invalid access key")

    token = await asyncio.to_thread(create_session, OWNER_USER_ID)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite="strict",
        path="/",
    )


@router.delete("/session", status_code=204)
async def logout(request: Request, response: Response):
    """Delete the session row and clear the cookie. Always allowed."""
    settings = get_settings()
    await asyncio.to_thread(delete_session, request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=settings.AUTH_COOKIE_SECURE,
        httponly=True,
        samesite="strict",
    )
