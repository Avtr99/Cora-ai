"""Monotonic revision counters persisted in the ``app_settings`` table.

Three counters are maintained:

- ``corpus_revision`` — bumped once per ingestion batch (after a successful
  Qdrant upsert) so the query cache key changes when the indexed corpus
  changes. See ``src/document_store/indexer.py``.
- ``config_revision`` — bumped whenever an operator changes the embedding,
  reranker, or answer-generation LLM model via the Settings UI, so cached
  answers from the old model stack are not served. See the settings routes in
  ``src/api/settings_routes/``.
- ``config_version`` — bumped on every ``reload_settings()`` call (i.e. any
  Settings UI save). It is an observability stamp returned on query responses
  and the settings status endpoint, and is also folded into the query cache
  key so cached responses do not serve a stale version stamp.

All are stored as integer strings in the existing ``app_settings`` key-value
 table, so they survive process restarts without a dedicated migration. The
query cache folds these into its key material (see ``src/utils/cache.py``),
which means a revision bump automatically invalidates stale entries (the key
no longer matches) without requiring a full table clear.
"""

import logging

from .database import get_connection

logger = logging.getLogger(__name__)

CORPUS_REVISION_KEY = "corpus_revision"
CONFIG_REVISION_KEY = "config_revision"
CONFIG_VERSION_KEY = "config_version"

_REVISION_KEYS = (CORPUS_REVISION_KEY, CONFIG_REVISION_KEY, CONFIG_VERSION_KEY)


def get_revisions() -> dict:
    """Read all revision/version counters in a single DB round-trip.

    Returns a dict keyed by ``CORPUS_REVISION_KEY`` / ``CONFIG_REVISION_KEY`` /
    ``CONFIG_VERSION_KEY`` plus ``config_version_updated_at``, defaulting to
    ``0`` / ``None`` when the rows are missing or the DB is unavailable.
    """
    result = {
        CORPUS_REVISION_KEY: 0,
        CONFIG_REVISION_KEY: 0,
        CONFIG_VERSION_KEY: 0,
        f"{CONFIG_VERSION_KEY}_updated_at": None,
    }
    try:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT key, value, updated_at FROM app_settings WHERE key IN (?, ?, ?)",
                _REVISION_KEYS,
            )
            for row in cursor.fetchall():
                k = row["key"]
                try:
                    result[k] = int(row["value"])
                except (ValueError, TypeError):
                    logger.warning("Invalid revision value for %s: %r", k, row["value"])
                if k == CONFIG_VERSION_KEY:
                    result[f"{k}_updated_at"] = row["updated_at"]
        finally:
            conn.close()
    except Exception as e:
        logger.debug("Could not read revisions: %s", e)
    return result


def bump_revision(key: str) -> int:
    """Atomically increment a revision counter and return the new value.

    Uses a single SQLite UPSERT. The ``app_settings`` table is created by
    migrations; if it is missing the call raises and the caller decides how to
    handle it.
    """
    if key not in _REVISION_KEYS:
        raise ValueError(f"Unknown revision key: {key!r}")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO app_settings (key, value, updated_at) "
            "VALUES (?, '1', CURRENT_TIMESTAMP) "
            "ON CONFLICT(key) DO UPDATE SET "
            "  value = CAST(CAST(value AS INTEGER) + 1 AS TEXT), "
            "  updated_at = CURRENT_TIMESTAMP",
            (key,),
        )
        conn.commit()
        row = cursor.execute(
            "SELECT value FROM app_settings WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return 1
        try:
            return int(row["value"])
        except (ValueError, TypeError):
            return 1
    finally:
        conn.close()


def bump_corpus_revision() -> int:
    return bump_revision(CORPUS_REVISION_KEY)


def bump_config_revision() -> int:
    return bump_revision(CONFIG_REVISION_KEY)


def bump_config_version() -> int:
    """Bump the config-version observability counter.

    Called by ``reload_settings()`` (and therefore every Settings UI save) so
    query responses and the settings status endpoint can report which config
    generation a request started under.
    """
    return bump_revision(CONFIG_VERSION_KEY)
