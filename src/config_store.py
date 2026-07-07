"""Runtime settings management: singleton, DB overlay, per-collection thresholds.

The ``Settings`` schema lives in ``config.py``; this module handles everything
that happens *after* the schema is loaded — overlaying DB-stored values on top
of env values, managing the thread-safe singleton, and resolving per-collection
relevance threshold overrides.
"""

import json
import logging
import secrets
from threading import Lock
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from .config import Settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton + DB overlay
# ---------------------------------------------------------------------------

_settings_instance: Optional[Settings] = None
_settings_lock = Lock()

# Keys stored in the app_settings table for embedding/search/reranker config.
# These overlay the .env values so users can change them from the UI.
DB_SETTING_KEYS = {
    "embedding_provider": "EMBEDDING_PROVIDER",
    "embedding_model": "EMBEDDING_MODEL",
    "embedding_dim": "EMBEDDING_DIM",
    "ollama_base_url": "OLLAMA_BASE_URL",
    "voyage_api_key": "VOYAGE_API_KEY",
    "cohere_api_key": "COHERE_API_KEY",
    "openai_api_key": "OPENAI_API_KEY",
    "rerank_provider": "RERANK_PROVIDER",
    "rerank_model": "RERANK_MODEL",
    "search_provider": "SEARCH_PROVIDER",
    "tavily_api_key": "TAVILY_API_KEY",
}


def _apply_db_overlay(settings: Settings) -> Settings:
    """Overlay DB-stored values on top of the env-loaded Settings.

    Reads from the ``app_settings`` SQLite table and overrides the matching
    Settings attributes.  This lets users change embedding/search/reranker
    config from the UI without editing .env.

    Also auto-generates and persists a ``SECRET_KEY`` on first run if none is
    configured in ``.env`` or the DB. The generated key is stable across
    restarts (stored in ``app_settings``) so conversation memory and history
    signatures remain valid. An explicit ``SECRET_KEY`` in ``.env`` always
    takes precedence and is never overwritten.

    Silently skips if the DB or table is unavailable (e.g. on first run
    before migrations have applied).
    """
    try:
        from .db.database import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT key, value FROM app_settings WHERE key IN (%s)"
                % ",".join("?" * len(DB_SETTING_KEYS)),
                tuple(DB_SETTING_KEYS.keys()),
            )
            for row in cursor.fetchall():
                db_key = row["key"]
                value = row["value"]
                attr_name = DB_SETTING_KEYS.get(db_key)
                if not attr_name:
                    continue
                # Type-convert based on the target field
                current = getattr(settings, attr_name, None)
                if isinstance(current, int):
                    try:
                        value = int(value)
                    except (ValueError, TypeError):
                        continue
                # Override the attribute on the pydantic model
                object.__setattr__(settings, attr_name, value)

            # Auto-generate SECRET_KEY if not configured anywhere.
            # An explicit .env value takes precedence (already on settings).
            # A previously generated DB value is reused (stable across restarts).
            if not getattr(settings, "SECRET_KEY", None):
                cursor.execute(
                    "SELECT value FROM app_settings WHERE key = 'secret_key'"
                )
                row = cursor.fetchone()
                if row:
                    object.__setattr__(settings, "SECRET_KEY", row["value"])
                else:
                    generated = secrets.token_hex(32)
                    cursor.execute(
                        "INSERT INTO app_settings (key, value, updated_at) "
                        "VALUES ('secret_key', ?, CURRENT_TIMESTAMP)",
                        (generated,),
                    )
                    conn.commit()
                    object.__setattr__(settings, "SECRET_KEY", generated)
                    logger.info(
                        "Auto-generated SECRET_KEY and persisted to app_settings — "
                        "set SECRET_KEY in .env to use your own key instead."
                    )
        finally:
            conn.close()
    except Exception:
        # DB not ready yet (first run, migrations not applied, etc.)
        # — silently fall back to .env values
        pass
    return settings


def get_settings() -> Settings:
    """Get or create the Settings singleton (thread-safe).

    After loading from .env, overlays any DB-stored values from the
    ``app_settings`` table so UI-configured settings take precedence.
    """
    global _settings_instance

    # Fast path: already initialized
    if _settings_instance is not None:
        return _settings_instance

    # Double-checked locking for thread-safe initialization
    with _settings_lock:
        if _settings_instance is None:
            _settings_instance = Settings()
            _apply_db_overlay(_settings_instance)

    return _settings_instance


def reload_settings() -> Settings:
    """Re-read DB overlay and update the singleton.

    Call this after saving settings via the API so the new values take
    effect without requiring a full server restart.
    """
    global _settings_instance
    with _settings_lock:
        if _settings_instance is not None:
            _apply_db_overlay(_settings_instance)
    return _settings_instance


def reset_settings_singleton() -> None:
    """Clear the cached Settings singleton. Used by tests to isolate state."""
    global _settings_instance
    with _settings_lock:
        _settings_instance = None


# ---------------------------------------------------------------------------
# Per-collection relevance threshold overrides
# ---------------------------------------------------------------------------

class _CollectionRelevanceOverrides(BaseModel):
    """Validated per-collection relevance threshold overrides."""

    kb_min_top_relevance_score: Optional[float] = Field(default=None, alias="KB_MIN_TOP_RELEVANCE_SCORE")
    rerank_score_threshold: Optional[float] = Field(default=None, alias="RERANK_SCORE_THRESHOLD")
    citation_min_relevance_score: Optional[float] = Field(default=None, alias="CITATION_MIN_RELEVANCE_SCORE")
    similarity_threshold: Optional[float] = Field(default=None, alias="SIMILARITY_THRESHOLD")

    model_config = {"populate_by_name": True}


# Cache for parsed COLLECTION_RELEVANCE_OVERRIDES, keyed by the raw JSON
# string. The settings singleton is stable for the process lifetime, so this
# avoids re-parsing the same JSON on every retrieval hot-path call to
# ``get_collection_threshold``. Invalidated automatically if the raw string
# changes (e.g. after ``reload_settings``).
_collection_overrides_cache: Dict[str, Dict[str, Any]] = {}


def _parse_collection_relevance_overrides(settings: Settings) -> Dict[str, Dict[str, Any]]:
    """Parse and validate the COLLECTION_RELEVANCE_OVERRIDES JSON string.

    Results are memoized in a module-level cache keyed by the raw JSON string
    so the retrieval hot path does not re-parse on every call. Invalid override
    entries are dropped individually so one bad collection does not break the
    others.
    """
    raw = getattr(settings, "COLLECTION_RELEVANCE_OVERRIDES", None) or ""
    cached = _collection_overrides_cache.get(raw)
    if cached is not None:
        return cached

    result: Dict[str, Dict[str, Any]] = {}
    if raw:
        try:
            parsed = json.loads(raw)
        except Exception as e:
            logger.warning("Failed to parse COLLECTION_RELEVANCE_OVERRIDES: %s", e)
            parsed = {}

        if isinstance(parsed, dict):
            for name, overrides in parsed.items():
                if not isinstance(overrides, dict):
                    logger.warning(
                        "Ignoring invalid COLLECTION_RELEVANCE_OVERRIDES entry for '%s': expected object",
                        name,
                    )
                    continue
                try:
                    validated = _CollectionRelevanceOverrides(**overrides)
                    result[name] = validated.model_dump(by_alias=True, exclude_none=True)
                except Exception as e:
                    logger.warning(
                        "Invalid COLLECTION_RELEVANCE_OVERRIDES for '%s': %s", name, e
                    )

    _collection_overrides_cache[raw] = result
    return result


def get_collection_threshold(settings: Settings, threshold_name: str, collection_name: Optional[str] = None) -> Any:
    """Return a relevance threshold, optionally overridden per collection.

    Args:
        settings: Settings singleton.
        threshold_name: Name of the threshold attribute on Settings (e.g.
            "KB_MIN_TOP_RELEVANCE_SCORE").
        collection_name: Optional collection name to look up in
            COLLECTION_RELEVANCE_OVERRIDES. Defaults to QDRANT_COLLECTION_NAME.

    Returns:
        The threshold value, using the per-collection override if present,
        otherwise the global setting.
    """
    if collection_name is None:
        collection_name = getattr(settings, "QDRANT_COLLECTION_NAME", None)
    overrides = _parse_collection_relevance_overrides(settings)
    collection_overrides = overrides.get(collection_name) if collection_name else None
    if isinstance(collection_overrides, dict) and threshold_name in collection_overrides:
        return collection_overrides[threshold_name]
    return getattr(settings, threshold_name, None)
