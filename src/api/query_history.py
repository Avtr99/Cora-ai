"""Server-side chat history helpers shared by all query paths (Phase 7).

``open_turn`` resolves the caller's identity, owns the ``conversation_id``
ownership check (a foreign chat 404s, D33), and loads server-side history.
``close_turn`` stores the turn when the result is worth keeping (A8). The
client no longer sends history — it is read from the ``chat_turns`` table.
"""

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Request

from ..db.chats import get_chat_owner, load_history, record_turn
from .auth.session_auth import current_user_id
from .query_models import Message, Query, Response

TRUSTED_HISTORY_ROLES = {"user", "assistant"}
HISTORY_CONTEXT_MAX_MESSAGES = 10


@dataclass(frozen=True)
class TurnContext:
    """Resolved identity and history for one query turn."""

    user_id: str
    conversation_id: str
    message_id: str
    history: List[Message]


async def open_turn(query: Query, request: Request) -> TurnContext:
    """Resolve the turn's identity and load its server-side history.

    A ``conversation_id`` owned by another user raises HTTP 404 (D33). A new
    conversation starts with empty history; an existing one replays the last
    ``HISTORY_CONTEXT_MAX_MESSAGES // 2`` turns, minus the in-flight
    ``message_id`` (a retry sees the chat without its own row).
    """
    user_id = current_user_id(request)
    conversation_id = query.conversation_id or str(uuid.uuid4())
    message_id = query.message_id or str(uuid.uuid4())

    owner = await asyncio.to_thread(get_chat_owner, conversation_id)
    if owner is not None and owner != user_id:
        raise HTTPException(status_code=404, detail="Chat not found")

    history: List[Message] = []
    if owner == user_id:
        raw_history = await asyncio.to_thread(
            load_history, conversation_id, message_id, HISTORY_CONTEXT_MAX_MESSAGES
        )
        history = sanitize_history_messages(
            [Message(role=m["role"], content=m["content"]) for m in raw_history]
        )

    return TurnContext(
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        history=history,
    )


def is_storable(raw_result: Dict[str, Any]) -> bool:
    """Decide from the raw orchestrator result whether the turn is kept (A8).

    Reads the raw result, not the sanitized response: ``query_service`` fills
    empty ``sources`` with ``["knowledge_base"]`` and ``timeout_exceeded`` is
    set on complete-but-slow answers — neither is a failure signal here.
    """
    return not raw_result.get("error") and "error_fallback" not in (
        raw_result.get("sources") or []
    )


async def close_turn(
    ctx: TurnContext, user_text: str, response: Response, raw_result: Dict[str, Any]
) -> None:
    """Store the sanitized response as this turn's row when storable.

    ``user_text`` is the exact text the client sent (``query.text``), as the
    old signing code used. A ``ChatNotFound`` from ``record_turn`` (ownership
    race) propagates — it must not be swallowed.
    """
    if is_storable(raw_result):
        await asyncio.to_thread(
            record_turn,
            ctx.user_id,
            ctx.conversation_id,
            ctx.message_id,
            user_text,
            response.model_dump(),
        )


def sanitize_history_messages(
    history: Optional[List[Message]], max_msg_len: int = 4000
) -> List[Message]:
    """
    Enforce length limits on history messages.
    Messages come from the server-side store, so they were sanitized on entry.

    Default 4000 chars/message * 10 history messages gives a ~40k char history
    block. Gemini Flash has a 1M context window, so this is a conservative prompt
    budget while still avoiding the old 2000-char truncation that cut long
    assistant answers in half during follow-ups.
    """
    if not history:
        return []

    filtered_messages = []

    for message in history:
        role = message.role
        if role not in TRUSTED_HISTORY_ROLES:
            continue
        content = (message.content or "").strip()

        if content:
            if len(content) > max_msg_len:
                content = content[:max_msg_len] + "..."

            filtered_messages.append(Message(role=role, content=content))

    return filtered_messages


def format_history_string(messages: List[Message]) -> str:
    """Format sanitized messages into a context string."""
    lines = []
    for message in messages:
        if message.content:
            lines.append(f"{message.role}: {message.content}")
    return "\n".join(lines)
