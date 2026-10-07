"""Self-service account routes.

Mounted under ``/v1`` and ``/api`` — both protected prefixes, so the
security middleware authenticates the request before these handlers run.
"""
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from pydantic import BaseModel, Field

from ..db.users import get_password_hash, set_password
from .auth.credentials import Password, hash_password_async, verify_password_async
from .auth.login_limiter import require_attempt
from .auth.session_auth import (
    SESSION_COOKIE,
    current_user_id,
    delete_sessions,
    require_protection,
)

router = APIRouter(
    prefix="/account",
    tags=["Account"],
    dependencies=[Depends(require_protection)],
)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: Password


@router.put("/password", status_code=204)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    user_id: str = Depends(current_user_id),
):
    """Change the caller's own password; every other session ends.

    The current session survives via ``keep_token``. With ``X-API-Key`` auth
    there is no cookie, so ``keep_token`` is None and all of the owner's
    sessions are deleted — acceptable for a script-driven reset.
    """
    require_attempt("password", user_id)

    stored_hash = await asyncio.to_thread(get_password_hash, user_id)
    ok = await verify_password_async(body.current_password, stored_hash)
    if not ok:
        # 400, not 401: a 401 must keep meaning "not authenticated" — the
        # frontend treats every 401 as a dead session and signs the user out.
        raise HTTPException(status_code=400, detail="Current password is wrong")

    password_hash = await hash_password_async(body.new_password)
    await asyncio.to_thread(set_password, user_id, password_hash)
    logger.info("Password changed for {}", user_id)
    await asyncio.to_thread(
        delete_sessions, user_id, request.cookies.get(SESSION_COOKIE)
    )
