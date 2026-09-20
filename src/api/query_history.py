"""History parsing and sanitization helpers for query requests."""

from typing import List, Optional, Tuple

from loguru import logger

from ..utils.security import verify_history_signature
from .query_models import Message

TRUSTED_HISTORY_ROLES = {"user", "assistant"}


def resolve_trusted_history(
    history: Optional[List[Message]],
    *,
    conversation_id: Optional[str],
    history_signature: Optional[str],
    signing_secret: Optional[str],
    scope_key: str = "",
    max_messages: int = 10,
) -> Tuple[Optional[List[Message]], bool]:
    """Verify client-provided history and discard it unless its signature is trusted."""
    if not history:
        return None, False
    if not signing_secret:
        logger.warning("History signing secret not configured. Discarding untrusted history.")
        return None, False
    if not conversation_id:
        logger.warning("History provided without conversation_id. Discarding unassociated history.")
        return None, False
    if not history_signature:
        logger.warning("History provided without signature. Discarding untrusted history.")
        return None, False

    history_window = history[-max_messages:]
    history_list = [
        {"role": message.role, "content": message.content}
        for message in history_window
    ]
    if not verify_history_signature(
        history_list,
        conversation_id,
        history_signature,
        signing_secret,
        scope_key=scope_key,
    ):
        logger.warning(
            f"History signature verification FAILED for conversation {conversation_id}. "
            "Discarding untrusted history."
        )
        return None, False

    logger.debug(f"History signature verified for conversation {conversation_id}")
    return [
        message for message in history_window
        if message.role in TRUSTED_HISTORY_ROLES
    ], True


def sanitize_history_messages(
    history: Optional[List[Message]], max_msg_len: int = 4000
) -> List[Message]:
    """
    Enforce length limits on history messages.
    Full threat sanitization is skipped here because history is cryptographically
    verified in query_service.py and was sanitized upon initial entry.

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


def format_history_context(
    history: Optional[List[Message]], max_msg_len: int = 4000
) -> Tuple[str, List[Message]]:
    """
    Legacy wrapper: Format recent conversation history for short-term context with sanitization.
    Returns (formatted_string, list_of_messages).
    """
    cleaned_messages = sanitize_history_messages(history, max_msg_len)
    history_str = format_history_string(cleaned_messages)
    return history_str, cleaned_messages
