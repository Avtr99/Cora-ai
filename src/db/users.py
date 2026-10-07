"""SQLite persistence for the single owner account.

The ``users`` table and the ``ON DELETE CASCADE`` foreign keys from
``auth_sessions``, ``async_query_jobs``, and ``chats`` are created by
migration ``011_users_and_chats.sql``; migration ``012_single_owner.sql``
removes any member rows. There is exactly one account — the owner.
All functions are synchronous and run inside ``asyncio.to_thread`` from the
API layer, like ``src/db/chats.py``.
"""

import sqlite3
from typing import Any, Dict, List, Optional

from .database import get_connection

# The built-in user every request acts as when protection is off. A
# partial unique index in migration 011 keeps this the only owner row.
OWNER_USER_ID = "owner"


class UsernameTaken(Exception):
    """The username is already used by another account."""


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Return ``id``/``username``/``role``/``password_hash``, or None.

    The only read that exposes ``password_hash`` — for the login verify.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, username, role, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_password_hash(user_id: str) -> Optional[str]:
    """Return ``user_id``'s stored password hash, or None.

    None means either an unknown user or an unclaimed owner — callers verify
    against the dummy hash either way, so no timing distinction leaks.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return row["password_hash"] if row else None
    finally:
        conn.close()


def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    """Return ``id``/``username``/``role``/``has_password``, or None."""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT id, username, role, password_hash IS NOT NULL AS has_password
            FROM users WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["has_password"] = bool(result["has_password"])
        return result
    finally:
        conn.close()


def list_users() -> List[Dict[str, Any]]:
    """Return ``id``/``username``/``role``/``created_at``, owner first then by ``username``.

    Never returns ``password_hash``.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, username, role, created_at
            FROM users
            ORDER BY role != 'owner', username
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def owner_claimed() -> bool:
    """Return True when the owner row has a password set."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT password_hash IS NOT NULL FROM users WHERE id = ?",
            (OWNER_USER_ID,),
        ).fetchone()
        return bool(row[0]) if row else False
    finally:
        conn.close()


def claim_owner(username: str, password_hash: str) -> bool:
    """Claim the owner row: set its username and password. False when already claimed.

    Only an unclaimed owner row (``password_hash IS NULL``) is updated.
    A duplicate ``username`` raises ``UsernameTaken``.
    """
    conn = get_connection()
    try:
        try:
            cursor = conn.execute(
                """
                UPDATE users SET username = ?, password_hash = ?
                WHERE id = ? AND password_hash IS NULL
                """,
                (username, password_hash, OWNER_USER_ID),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            raise UsernameTaken(username) from exc
        return cursor.rowcount > 0
    finally:
        conn.close()


def set_password(user_id: str, password_hash: str) -> bool:
    """Replace ``user_id``'s password hash. Returns False for unknown IDs."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (password_hash, user_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
