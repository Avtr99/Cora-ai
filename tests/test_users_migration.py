"""Tests for migration 011: users table, rebuilt auth_sessions/async_query_jobs."""
import os
import sqlite3
from pathlib import Path

import pytest

from src.api.auth.session_auth import create_session
from src.db.users import OWNER_USER_ID
from src.api.middleware.security import generate_api_key
from src.config import reset_settings_singleton
from src.db.database import get_connection, run_migrations

_MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"
_MIGRATION_011 = "011_users_and_chats.sql"
_MIGRATION_012 = "012_single_owner.sql"


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Isolated SQLite file with a configured API key (for session inserts)."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'cora.db'}")
    monkeypatch.setenv("API_ACCESS_KEY", generate_api_key())
    reset_settings_singleton()
    yield
    reset_settings_singleton()


def _apply_migrations_before(stop_file: str) -> None:
    """Replay every migration older than ``stop_file`` on the current DB."""
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        for name in sorted(f for f in os.listdir(_MIGRATIONS_DIR) if f.endswith(".sql")):
            if name >= stop_file:
                break
            conn.executescript((_MIGRATIONS_DIR / name).read_text(encoding="utf-8"))
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations (version) VALUES (?)",
                (name,),
            )
        conn.commit()
    finally:
        conn.close()


class TestUsersTable:
    def test_owner_row_seeded(self, tmp_db):
        run_migrations()
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id, username, role FROM users"
            ).fetchall()
        finally:
            conn.close()
        assert [dict(row) for row in rows] == [
            {"id": OWNER_USER_ID, "username": "owner", "role": "owner"}
        ]

    def test_second_owner_rejected(self, tmp_db):
        """The partial unique index allows exactly one owner row."""
        run_migrations()
        conn = get_connection()
        try:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO users (id, username, role) "
                    "VALUES ('owner-2', 'owner2', 'owner')"
                )
            # Members are not constrained by the owner index.
            conn.execute(
                "INSERT INTO users (id, username, role) "
                "VALUES ('member-1', 'member1', 'member')"
            )
            conn.commit()
        finally:
            conn.close()


class TestUpgradeFrom010:
    def test_011_rebuilds_auth_sessions_with_user_id(self, tmp_db):
        """A DB at migration 010 keeps no session rows after 011."""
        _apply_migrations_before(_MIGRATION_011)

        conn = get_connection()
        try:
            conn.execute(
                """
                INSERT INTO auth_sessions (token_hash, key_fingerprint, expires_at)
                VALUES ('old-token', 'old-fingerprint', datetime('now', '+1 day'))
                """
            )
            conn.execute(
                """
                INSERT INTO async_query_jobs (job_id, status, submitted_at, payload)
                VALUES ('old-job', 'queued', '2026-01-01', '{}')
                """
            )
            conn.commit()
        finally:
            conn.close()

        run_migrations()

        conn = get_connection()
        try:
            applied = {
                row["version"]
                for row in conn.execute("SELECT version FROM schema_migrations")
            }
            session_cols = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(auth_sessions)")
            }
            job_cols = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(async_query_jobs)")
            }
            session_rows = conn.execute("SELECT * FROM auth_sessions").fetchall()
            job_rows = conn.execute("SELECT * FROM async_query_jobs").fetchall()
        finally:
            conn.close()

        assert _MIGRATION_011 in applied
        assert "user_id" in session_cols
        assert "user_id" in job_cols
        assert session_rows == []
        assert job_rows == []


class TestSingleOwnerMigration:
    def test_012_retires_member_rows(self, tmp_db):
        """Upgrading an 011 DB with members: their chats and jobs move to the
        owner, their sessions end, and the member rows are removed."""
        _apply_migrations_before(_MIGRATION_012)

        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO users (id, username, role, password_hash) "
                "VALUES ('m1', 'alice', 'member', 'hash')"
            )
            conn.execute(
                "INSERT INTO auth_sessions (token_hash, user_id, key_fingerprint, expires_at) "
                "VALUES ('t1', 'm1', 'fp', datetime('now', '+1 day'))"
            )
            conn.execute(
                "INSERT INTO chats (id, user_id, title) VALUES ('c1', 'm1', 'member chat')"
            )
            conn.execute(
                "INSERT INTO async_query_jobs "
                "(job_id, user_id, status, submitted_at, payload) "
                "VALUES ('j1', 'm1', 'queued', '2026-01-01', '{}')"
            )
            conn.commit()
        finally:
            conn.close()

        run_migrations()

        conn = get_connection()
        try:
            users = conn.execute("SELECT id, role FROM users").fetchall()
            chat_owner = conn.execute(
                "SELECT user_id FROM chats WHERE id = 'c1'"
            ).fetchone()[0]
            job_owner = conn.execute(
                "SELECT user_id FROM async_query_jobs WHERE job_id = 'j1'"
            ).fetchone()[0]
            sessions = conn.execute("SELECT * FROM auth_sessions").fetchall()
        finally:
            conn.close()

        assert [dict(row) for row in users] == [
            {"id": OWNER_USER_ID, "role": "owner"}
        ]
        assert chat_owner == OWNER_USER_ID
        assert job_owner == OWNER_USER_ID
        assert sessions == []


class TestUserCascade:
    def test_deleting_owner_removes_sessions(self, tmp_db):
        """auth_sessions rows go away with their user (ON DELETE CASCADE)."""
        run_migrations()
        create_session(OWNER_USER_ID)

        conn = get_connection()
        try:
            conn.execute("DELETE FROM users WHERE id = ?", (OWNER_USER_ID,))
            conn.commit()
            rows = conn.execute("SELECT * FROM auth_sessions").fetchall()
        finally:
            conn.close()

        assert rows == []
