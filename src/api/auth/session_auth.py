"""Shared API-key and browser-session helpers.

When ``ENABLE_API_KEY_PROTECTION`` is on, a browser signs in with a username
and password and gets an opaque session token in an HttpOnly cookie. The
instance access key claims the owner account once and stays for scripts via
``X-API-Key``. Sessions are rows in the ``auth_sessions``
table: sign-out deletes the row on the server, and key rotation invalidates
every session because each row is pinned to the key's SHA-256 fingerprint.
"""
import hashlib
import secrets
from datetime import timedelta

from fastapi import HTTPException, Request

from ...config import get_settings
from ...db.database import get_connection
from ...db.users import OWNER_USER_ID

SESSION_COOKIE = "cora_session"
SESSION_TTL = timedelta(days=7)


def _credential_hash(value: str) -> str:
    """SHA-256 fingerprint of a high-entropy credential (API key or session token).

    A fast unsalted hash is correct here: these are 256-bit random values
    (``secrets.token_hex(32)`` / ``secrets.token_urlsafe(32)``), not
    user-chosen passwords, so there is no brute-force surface for a salted
    KDF to defend. A slow KDF would add per-request latency for no benefit,
    and its salted output could not be looked up by hash anyway.
    """
    # codeql[py/weak-sensitive-data-hashing] -- high-entropy tokens, not passwords; see docstring
    return hashlib.sha256(value.encode()).hexdigest()


def key_matches(provided: str | None) -> bool:
    """Return True when ``provided`` equals the configured API access key.

    Comparison uses ``secrets.compare_digest`` to prevent timing attacks.
    """
    configured = get_settings().API_ACCESS_KEY
    if not provided or not configured:
        return False
    return secrets.compare_digest(
        _credential_hash(provided),
        _credential_hash(configured),
    )


def create_session(user_id: str) -> str:
    """Insert a session row for ``user_id`` and return the raw token for the cookie.

    Only the SHA-256 hash of the token is stored, so a database leak does
    not expose usable credentials. Expired rows are pruned in the same
    transaction.
    """
    api_key = get_settings().API_ACCESS_KEY
    token = secrets.token_urlsafe(32)
    conn = get_connection()
    try:
        conn.execute("DELETE FROM auth_sessions WHERE expires_at <= datetime('now')")
        conn.execute(
            """
            INSERT INTO auth_sessions (token_hash, user_id, key_fingerprint, expires_at)
            VALUES (?, ?, ?, datetime('now', '+' || ? || ' seconds'))
            """,
            (
                _credential_hash(token),
                user_id,
                _credential_hash(api_key or ""),
                int(SESSION_TTL.total_seconds()),
            ),
        )
        conn.commit()
        return token
    finally:
        conn.close()


def session_user_id(token: str | None) -> str | None:
    """Return the session's ``user_id`` when ``token`` is live for the current key.

    Same checks as before (token row, key fingerprint, expiry); ``None`` means
    the cookie does not authenticate the request.
    """
    api_key = get_settings().API_ACCESS_KEY
    if not token or not api_key:
        return None
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT user_id
            FROM auth_sessions
            WHERE token_hash = ?
              AND key_fingerprint = ?
              AND expires_at > datetime('now')
            """,
            (
                _credential_hash(token),
                _credential_hash(api_key),
            ),
        ).fetchone()
        return row["user_id"] if row else None
    finally:
        conn.close()


def is_cross_site_request(request: Request) -> bool:
    """Return True when a browser flagged this unsafe request as cross-site.

    CSRF guard for cookie-authenticated state-changing requests: browsers
    always send ``Sec-Fetch-Site``; reject anything cross-origin. Non-browser
    clients omit the header and are allowed, matching Go's
    ``net/http.CrossOriginProtection`` semantics.
    """
    fetch_site = request.headers.get("Sec-Fetch-Site")
    return (
        request.method not in ("GET", "HEAD", "OPTIONS")
        and fetch_site is not None
        and fetch_site not in ("same-origin", "none")
    )


def current_user_id(request: Request) -> str:
    """Return the request's user identity.

    With protection off, every request acts as the built-in owner. With
    protection on, ``SecurityMiddleware.dispatch`` has already set
    ``request.state.user_id``; a missing attribute means the middleware never
    ran, so the ``AttributeError`` propagates — fail closed, never fall back
    to the owner.
    """
    if not get_settings().ENABLE_API_KEY_PROTECTION:
        return OWNER_USER_ID
    return request.state.user_id


def require_owner(request: Request) -> str:
    """FastAPI dependency: return the request's user ID when it is the owner.

    403 otherwise. No DB read — the owner ID is the constant
    ``OWNER_USER_ID``.
    """
    user_id = current_user_id(request)
    if user_id != OWNER_USER_ID:
        raise HTTPException(status_code=403, detail="Owner only")
    return user_id


def require_owner_for_writes(request: Request) -> None:
    """FastAPI dependency: owner check for non-read methods on a router.

    Reads (GET/HEAD/OPTIONS) pass for every authenticated user; writes must
    come from the owner.
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    require_owner(request)


def reject_cross_site(request: Request) -> None:
    """FastAPI dependency: 403 when a browser flagged this request cross-site.

    For auth-excluded routes (login, owner claim) the middleware's CSRF guard
    never runs — without this check a cross-site POST could plant a session
    cookie in a victim's browser (login CSRF).
    """
    if is_cross_site_request(request):
        raise HTTPException(status_code=403, detail="Cross-origin request rejected")


def require_protection() -> None:
    """FastAPI dependency: 404 when API-key protection is off.

    With no login there is no account, so the account routes do not exist.
    """
    if not get_settings().ENABLE_API_KEY_PROTECTION:
        raise HTTPException(status_code=404, detail="Endpoint not available")


def delete_sessions(user_id: str, keep_token: str | None = None) -> None:
    """Delete all of ``user_id``'s sessions, except ``keep_token``'s when given."""
    conn = get_connection()
    try:
        if keep_token is None:
            conn.execute(
                "DELETE FROM auth_sessions WHERE user_id = ?", (user_id,)
            )
        else:
            conn.execute(
                "DELETE FROM auth_sessions WHERE user_id = ? AND token_hash != ?",
                (user_id, _credential_hash(keep_token)),
            )
        conn.commit()
    finally:
        conn.close()


def delete_session(token: str | None) -> None:
    """Delete the session row for ``token``. No-op when ``token`` is empty."""
    if not token:
        return
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM auth_sessions WHERE token_hash = ?",
            (_credential_hash(token),),
        )
        conn.commit()
    finally:
        conn.close()
