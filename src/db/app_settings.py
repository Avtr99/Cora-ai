"""Shared helper for reading/writing the app_settings key-value table.

Used by both the LLM factory (saving provider config) and the settings API
routes (saving embedding/search/reranker config). Consolidates the duplicate
``CREATE TABLE IF NOT EXISTS`` + upsert/delete logic in one place.
"""

import logging
import re
from typing import Dict, Optional

from .database import get_connection

logger = logging.getLogger(__name__)

# Safe key format: no spaces, control chars, or SQL special characters.
_SETTING_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]+$")

# Well-known setting keys persisted by the application.  Dynamic sub-system
# keys (e.g. saved LLM profiles) are matched by ``_DYNAMIC_KEY_PATTERNS``.
_KNOWN_SETTING_KEYS = frozenset(
    {
        # Embedding / reranker / search — scoped API keys per subsystem so the
        # embeddings and reranker routes never share a DB row. See
        # docs/ROADMAP_FRAGILITY_AUDIT.md (P0 shared-key fix).
        "embedding_provider",
        "embedding_model",
        "embedding_dim",
        "ollama_base_url",
        "embedding_voyage_api_key",
        "embedding_cohere_api_key",
        "embedding_openai_api_key",
        "rerank_provider",
        "rerank_model",
        "reranker_voyage_api_key",
        "reranker_cohere_api_key",
        "search_provider",
        "tavily_api_key",
        # Legacy shared key names — kept readable so migration 009 can copy
        # their values into the scoped keys. Not written by any route after
        # the P0 fix; retained for the one-time backfill only.
        "voyage_api_key",
        "cohere_api_key",
        "openai_api_key",
        # LLM
        "llm_provider",
        "llm_api_key",
        "llm_base_url",
        "llm_model_main",
        "llm_model_lite",
        "llm_model_relevance",
        "llm_organization",
        # Misc
        "secret_key",
        "ingest_worker_heartbeat",
        "config_version",
        "config_version_updated_at",
    }
)

# Dynamic keys that are allowed but not enumerated above.
_DYNAMIC_KEY_PATTERNS = (re.compile(r"^llm_profile_[a-zA-Z0-9_.-]+$"),)


def _is_known_setting_key(key: str) -> bool:
    """Return True if ``key`` is a well-known or dynamic-prefixed setting key."""
    if key in _KNOWN_SETTING_KEYS:
        return True
    return any(pattern.match(key) for pattern in _DYNAMIC_KEY_PATTERNS)


def _validate_setting_key(key: str) -> None:
    """Validate a setting key for reads and writes.

    Raises:
        ValueError: If the key is empty, has unsafe characters, or is not a
            recognized setting key.
    """
    if not key or not isinstance(key, str):
        raise ValueError("Setting key must be a non-empty string")

    if not _SETTING_KEY_PATTERN.match(key):
        raise ValueError(
            f"Setting key {key!r} contains disallowed characters "
            "(only letters, numbers, underscore, dot, and hyphen are permitted)"
        )

    if not _is_known_setting_key(key):
        raise ValueError(f"Unknown setting key: {key!r}")


def _ensure_app_settings_table(cursor) -> None:
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS app_settings ("
        "key TEXT PRIMARY KEY, value TEXT NOT NULL, "
        "updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )


def get_app_setting(key: str) -> Optional[str]:
    """Read a single key from the app_settings table (None if missing).

    Raises:
        ValueError: If ``key`` is empty, malformed, or not a recognized
            setting key. Typos therefore fail fast instead of returning None.
    """
    _validate_setting_key(key)

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row is not None else None
    except Exception:
        # DB not ready yet (first run, migrations not applied, etc.).
        logger.debug("Failed to read app_setting %r", key, exc_info=True)
        return None
    finally:
        conn.close()


def save_app_setting(key: str, value: Optional[str]) -> None:
    """Save or delete a single key in the app_settings table.

    If value is None, the key is deleted (falls back to .env default).

    Raises:
        ValueError: If ``key`` is not a recognized setting key.
    """
    _validate_setting_key(key)

    conn = get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            _ensure_app_settings_table(cursor)
            if value is None:
                cursor.execute("DELETE FROM app_settings WHERE key = ?", (key,))
            else:
                cursor.execute(
                    "INSERT INTO app_settings (key, value, updated_at) "
                    "VALUES (?, ?, CURRENT_TIMESTAMP) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
                    "updated_at = CURRENT_TIMESTAMP",
                    (key, value),
                )
    finally:
        conn.close()


def save_app_settings(settings_dict: Dict[str, Optional[str]]) -> None:
    """Write multiple keys to the app_settings table in a single transaction.

    Raises:
        ValueError: If any key is not a recognized setting key.
    """
    # Validate all keys before opening the transaction so a typo aborts cleanly.
    for key in settings_dict:
        _validate_setting_key(key)

    conn = get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            _ensure_app_settings_table(cursor)
            for key, value in settings_dict.items():
                if value is None:
                    cursor.execute("DELETE FROM app_settings WHERE key = ?", (key,))
                else:
                    cursor.execute(
                        "INSERT INTO app_settings (key, value, updated_at) "
                        "VALUES (?, ?, CURRENT_TIMESTAMP) "
                        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
                        "updated_at = CURRENT_TIMESTAMP",
                        (key, value),
                    )
    finally:
        conn.close()
