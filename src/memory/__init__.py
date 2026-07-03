"""
Conversation memory module using pluggable embeddings + Qdrant.

Uses lazy imports to reduce startup time.
Heavy dependencies (qdrant_client, embedding provider) are only loaded
when memory functions are actually called.
"""

# Lazy accessor - imports deferred until first call
_memory_client = None


def get_memory_client():
    """
    Get or create the singleton memory client.

    Uses lazy import to defer heavy dependencies until first use,
    reducing startup time.

    Returns:
        ConversationMemory instance
    """
    global _memory_client
    if _memory_client is None:
        # Lazy import for cold start optimization
        from .conversation_memory import ConversationMemory
        _memory_client = ConversationMemory.get_instance()
    return _memory_client


def __getattr__(name):
    """Lazy import for ConversationMemory and PIIRedactor class access."""
    if name == "ConversationMemory":
        from .conversation_memory import ConversationMemory
        # Cache in globals to avoid repeated __getattr__ calls
        globals()['ConversationMemory'] = ConversationMemory
        return ConversationMemory
    if name in ("PIIRedactor", "get_pii_redactor"):
        from .pii_redactor import PIIRedactor, get_pii_redactor
        # Cache both symbols to avoid redundant import paths
        globals()['PIIRedactor'] = PIIRedactor
        globals()['get_pii_redactor'] = get_pii_redactor
        return PIIRedactor if name == "PIIRedactor" else get_pii_redactor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["ConversationMemory", "get_memory_client", "PIIRedactor", "get_pii_redactor"]
