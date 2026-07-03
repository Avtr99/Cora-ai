"""Shared helper for reading/writing the app_settings key-value table.

Used by both the LLM factory (saving provider config) and the settings API
routes (saving embedding/search/reranker config). Consolidates the duplicate
``CREATE TABLE IF NOT EXISTS`` + upsert/delete logic in one place.
"""

from typing import Dict, Optional

from .database import get_connection


def save_app_setting(key: str, value: Optional[str]) -> None:
    """Save or delete a single key in the app_settings table.

    If value is None, the key is deleted (falls back to .env default).
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS app_settings ("
            "key TEXT PRIMARY KEY, value TEXT NOT NULL, "
            "updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
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
        conn.commit()
    finally:
        conn.close()


def save_app_settings(settings_dict: Dict[str, Optional[str]]) -> None:
    """Write multiple keys to the app_settings table in a single transaction."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS app_settings ("
            "key TEXT PRIMARY KEY, value TEXT NOT NULL, "
            "updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
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
        conn.commit()
    finally:
        conn.close()
