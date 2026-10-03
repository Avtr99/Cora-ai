"""Shared API-key and browser-session helpers.

When ``ENABLE_API_KEY_PROTECTION`` is on, a browser logs in once with the
instance access key and gets an opaque session token in an HttpOnly cookie.
Scripts keep using ``X-API-Key``. Sessions are rows in the ``auth_sessions``
table: sign-out deletes the row on the server, and key rotation invalidates
every session because each row is pinned to the key's SHA-256 fingerprint.
"""
import hashlib
import secrets
from datetime import timedelta

from fastapi import Request

from ...config import get_settings
from ...db.database import get_connection

SESSION_COOKIE = "cora_session"
SESSION_TTL = timedelta(days=7)

# The single built-in user every request acts as in Phase 7 (D15/D31). A
# partial unique index in migration 011 keeps this the only owner row.
OWNER_USER_ID = "owner"


def key_matches(provided: str | None) -> bool:
    """Return True when ``provided`` equals the configured API access key.

    SHA-256 is intentional here: API keys are high-entropy random tokens
    (256 bits via ``secrets.token_hex(32)``), not user passwords, so a
    fast hash is appropriate — there is no realistic brute-force surface.
    A slow KDF (PBKDF2/scrypt) would add per-request latency for no
    security benefit. Comparison uses ``secrets.compare_digest`` to
    prevent timing attacks.
    """
    configured = get_settings().API_ACCESS_KEY
    if not provided or not configured:
        return False
    return secrets.compare_digest(
        hashlib.sha256(provided.encode()).hexdigest(),
        hashlib.sha256(configured.encode()).hexdigest(),
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
                hashlib.sha256(token.encode()).hexdigest(),
                user_id,
                hashlib.sha256(api_key.encode()).hexdigest(),
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
                hashlib.sha256(token.encode()).hexdigest(),
                hashlib.sha256(api_key.encode()).hexdigest(),
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

    With protection off, every request acts as the built-in owner (D15). With
    protection on, ``SecurityMiddleware.dispatch`` has already set
    ``request.state.user_id``; a missing attribute means the middleware never
    ran, so the ``AttributeError`` propagates — fail closed, never fall back
    to the owner.
    """
    if not get_settings().ENABLE_API_KEY_PROTECTION:
        return OWNER_USER_ID
    return request.state.user_id


def delete_session(token: str | None) -> None:
    """Delete the session row for ``token``. No-op when ``token`` is empty."""
    if not token:
        return
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM auth_sessions WHERE token_hash = ?",
            (hashlib.sha256(token.encode()).hexdigest(),),
        )
        conn.commit()
    finally:
        conn.close()
