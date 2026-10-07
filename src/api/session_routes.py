"""Browser session endpoints for API-key-protected deployments.

With ``ENABLE_API_KEY_PROTECTION`` on, a browser signs in with a username and
password and receives an HttpOnly session cookie (``cora_session``) backed by
a row in the ``auth_sessions`` table. The owner account is claimed once with
the instance access key; scripts keep using ``X-API-Key``. These
routes are mounted under ``/api`` and excluded from API-key enforcement in
``SecurityMiddleware``.
"""
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from loguru import logger
from pydantic import BaseModel, Field

from ..config import get_settings
from ..db.users import (
    OWNER_USER_ID,
    UsernameTaken,
    claim_owner,
    get_user,
    get_user_by_username,
    owner_claimed,
)
from .auth.credentials import (
    Password,
    Username,
    hash_password_async,
    verify_password_async,
)
from .auth.login_limiter import require_attempt
from .auth.session_auth import (
    SESSION_COOKIE,
    SESSION_TTL,
    create_session,
    delete_session,
    key_matches,
    reject_cross_site,
    require_protection,
    session_user_id,
)

router = APIRouter(prefix="/auth", tags=["Session"])

_INVALID_CREDENTIALS = "Invalid username or password"


class LoginRequest(BaseModel):
    username: Username
    password: str = Field(min_length=1, max_length=128)


class OwnerClaimRequest(BaseModel):
    api_key: str = Field(min_length=1, max_length=512)
    username: Username
    password: Password


def _public_user(row: dict | None) -> dict | None:
    """The only user fields a session-status response may expose."""
    if row is None:
        return None
    return {"id": row["id"], "username": row["username"], "role": row["role"]}


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        secure=get_settings().AUTH_COOKIE_SECURE,
        samesite="strict",
        path="/",
    )


@router.get("/session")
async def get_session(request: Request):
    """Report login requirement, auth state, and the current user.

    Never returns 401 — the SPA calls this to decide whether to show the
    login page, the owner-claim form, or the app. A valid ``X-API-Key``
    header counts as the owner; a session cookie resolves to its user.
    """
    settings = get_settings()
    protected = settings.ENABLE_API_KEY_PROTECTION
    if not protected or key_matches(request.headers.get("X-API-Key")):
        user_id = OWNER_USER_ID
    else:
        user_id = await asyncio.to_thread(
            session_user_id, request.cookies.get(SESSION_COOKIE)
        )
    user = await asyncio.to_thread(get_user, user_id) if user_id else None
    claim_required = protected and not await asyncio.to_thread(owner_claimed)
    return {
        "required": protected,
        "authenticated": user_id is not None,
        "owner_claim_required": claim_required,
        "user": _public_user(user),
    }


@router.post(
    "/session",
    status_code=204,
    dependencies=[Depends(require_protection), Depends(reject_cross_site)],
)
async def login(body: LoginRequest, request: Request, response: Response):
    """Sign in with a username and password; set the session cookie.

    Unknown users, wrong passwords, and the unclaimed owner all fail with the
    same 401 after exactly one argon2 verify — against a dummy hash when
    there is no stored hash — so neither the body nor the timing distinguishes
    them.
    """
    client_ip = request.client.host if request.client else "unknown"
    try:
        # Keyed on IP + username: an attacker spamming guesses burns their own
        # IP's budget instead of locking the owner out of their account.
        require_attempt("login", f"{client_ip}:{body.username}")
    except HTTPException:
        logger.warning(
            "Sign-in rate limited for {} from {}", body.username, client_ip
        )
        raise

    row = await asyncio.to_thread(get_user_by_username, body.username)
    ok = await verify_password_async(
        body.password, row["password_hash"] if row else None
    )
    if not ok:
        logger.warning(
            "Failed sign-in for {} from {}", body.username, client_ip
        )
        raise HTTPException(status_code=401, detail=_INVALID_CREDENTIALS)

    # Rotate: drop whatever cookie the browser presented before minting a
    # fresh session.
    await asyncio.to_thread(delete_session, request.cookies.get(SESSION_COOKIE))
    token = await asyncio.to_thread(create_session, row["id"])
    logger.info("Signed in {} from {}", body.username, client_ip)
    _set_session_cookie(response, token)


@router.post(
    "/owner",
    status_code=204,
    dependencies=[Depends(require_protection), Depends(reject_cross_site)],
)
async def claim_owner_account(
    body: OwnerClaimRequest, request: Request, response: Response
):
    """Claim the owner account with the instance access key.

    One-time setup: sets the owner row's username and password, then signs
    in. Not rate-limited — the key has 256 bits of entropy.
    """
    if await asyncio.to_thread(owner_claimed):
        raise HTTPException(status_code=409, detail="Owner account already set up")
    if not key_matches(body.api_key):
        raise HTTPException(status_code=401, detail="Invalid access key")

    password_hash = await hash_password_async(body.password)
    try:
        claimed = await asyncio.to_thread(claim_owner, body.username, password_hash)
    except UsernameTaken:
        raise HTTPException(status_code=409, detail="Username taken") from None
    if not claimed:
        raise HTTPException(status_code=409, detail="Owner account already set up")

    logger.info("Owner account claimed as {}", body.username)
    await asyncio.to_thread(delete_session, request.cookies.get(SESSION_COOKIE))
    token = await asyncio.to_thread(create_session, OWNER_USER_ID)
    _set_session_cookie(response, token)


@router.delete("/session", status_code=204, dependencies=[Depends(reject_cross_site)])
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
