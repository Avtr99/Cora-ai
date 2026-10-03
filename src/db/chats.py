"""SQLite persistence for server-side chats.

Chats are stored on the server under a user's ``user_id`` (Phase 7): one row
per turn in ``chat_turns``, upserted by message ID so a retry keeps its
position (A5/A9). All functions are synchronous and run inside
``asyncio.to_thread`` from the API layer. The tables are created by migration
``011_users_and_chats.sql``.
"""

import json
from typing import Any, Dict, List, Optional

from .database import get_connection


class ChatNotFound(Exception):
    """The chat does not exist, or belongs to another user (D33)."""


def answer_id(message_id: str) -> str:
    """Answer ID derived from the user message ID (A10). Only place this rule lives."""
    return f"{message_id}-answer"


def chat_title(text: str) -> str:
    """Chat title from the first user text: first 30 chars plus '...' (B3)."""
    return text if len(text) <= 30 else text[:30] + "..."


def get_chat_owner(chat_id: str) -> Optional[str]:
    """Return the ``user_id`` owning ``chat_id``, or None when it does not exist."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT user_id FROM chats WHERE id = ?", (chat_id,)
        ).fetchone()
        return row["user_id"] if row else None
    finally:
        conn.close()


def load_history(
    chat_id: str, exclude_message_id: str, max_messages: int
) -> List[Dict[str, str]]:
    """Return the last ``max_messages // 2`` turns as user/assistant message dicts.

    Oldest first. The turn with ``exclude_message_id`` (the in-flight retry)
    is skipped. Callers check chat ownership before calling this.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT user_text, json_extract(response_json, '$.answer') AS answer
            FROM chat_turns
            WHERE chat_id = ? AND message_id != ?
            ORDER BY seq DESC
            LIMIT ?
            """,
            (chat_id, exclude_message_id, max_messages // 2),
        ).fetchall()
    finally:
        conn.close()

    messages: List[Dict[str, str]] = []
    for row in reversed(rows):
        messages.append({"role": "user", "content": row["user_text"]})
        messages.append({"role": "assistant", "content": row["answer"]})
    return messages


def record_turn(
    user_id: str,
    chat_id: str,
    message_id: str,
    user_text: str,
    response: Dict[str, Any],
) -> None:
    """Record one user/assistant turn in a single transaction.

    Creates the chat on first turn (title from the first user text) and bumps
    ``updated_at`` on later turns. A turn whose ``message_id`` already exists
    is updated in place and keeps its ``seq`` — this is the retry path (A9).
    Raises ``ChatNotFound`` when the chat is owned by another user.
    """
    conn = get_connection()
    try:
        conn.execute("BEGIN")
        conn.execute(
            """
            INSERT INTO chats (id, user_id, title) VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
            WHERE chats.user_id = excluded.user_id
            """,
            (chat_id, user_id, chat_title(user_text)),
        )
        # Read the owner on this connection: a second connection would not see
        # the uncommitted insert above and could block on the write lock.
        owner_row = conn.execute(
            "SELECT user_id FROM chats WHERE id = ?", (chat_id,)
        ).fetchone()
        owner = owner_row["user_id"] if owner_row else None
        if owner != user_id:
            conn.rollback()
            raise ChatNotFound(chat_id)
        conn.execute(
            """
            INSERT INTO chat_turns (chat_id, message_id, seq, user_text, response_json)
            VALUES (?, ?, (SELECT COALESCE(MAX(seq), 0) + 1 FROM chat_turns WHERE chat_id = ?), ?, ?)
            ON CONFLICT(chat_id, message_id) DO UPDATE
            SET user_text = excluded.user_text, response_json = excluded.response_json
            """,
            (
                chat_id,
                message_id,
                chat_id,
                user_text,
                json.dumps(response, ensure_ascii=True, default=str),
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_chats(user_id: str) -> List[Dict[str, Any]]:
    """Return ``id``/``title``/``updated_at`` for the user's chats, newest first."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, title, updated_at
            FROM chats
            WHERE user_id = ?
            ORDER BY updated_at DESC
            """,
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_chat(user_id: str, chat_id: str) -> Optional[Dict[str, Any]]:
    """Return the chat with its turns ordered by ``seq``, or None."""
    conn = get_connection()
    try:
        chat_row = conn.execute(
            """
            SELECT id, title, created_at, updated_at
            FROM chats
            WHERE id = ? AND user_id = ?
            """,
            (chat_id, user_id),
        ).fetchone()
        if chat_row is None:
            return None
        turn_rows = conn.execute(
            """
            SELECT message_id, user_text, response_json, created_at
            FROM chat_turns
            WHERE chat_id = ?
            ORDER BY seq
            """,
            (chat_id,),
        ).fetchall()

        turns = [
            {
                "message_id": row["message_id"],
                "answer_id": answer_id(row["message_id"]),
                "user_text": row["user_text"],
                "response": json.loads(row["response_json"]),
                "created_at": row["created_at"],
            }
            for row in turn_rows
        ]
        return {
            "id": chat_row["id"],
            "title": chat_row["title"],
            "created_at": chat_row["created_at"],
            "updated_at": chat_row["updated_at"],
            "turns": turns,
        }
    finally:
        conn.close()


def delete_chat(user_id: str, chat_id: str) -> bool:
    """Delete the chat when it belongs to ``user_id``. Turns go by cascade."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM chats WHERE id = ? AND user_id = ?", (chat_id, user_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
