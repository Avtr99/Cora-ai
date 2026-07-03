"""History parsing and sanitization helpers for query requests."""

from typing import List, Optional, Tuple


from .query_models import Message


def sanitize_history_messages(
    history: Optional[List[Message]], max_msg_len: int = 2000
) -> List[Message]:
    """
    Enforce length limits on history messages.
    Full threat sanitization is skipped here because history is cryptographically 
    verified in query_service.py and was sanitized upon initial entry.
    """
    if not history:
        return []

    filtered_messages = []

    for message in history:
        role = message.role
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
    history: Optional[List[Message]], max_msg_len: int = 2000
) -> Tuple[str, List[Message]]:
    """
    Legacy wrapper: Format recent conversation history for short-term context with sanitization.
    Returns (formatted_string, list_of_messages).
    """
    cleaned_messages = sanitize_history_messages(history, max_msg_len)
    history_str = format_history_string(cleaned_messages)
    return history_str, cleaned_messages
