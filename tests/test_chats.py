"""Tests for src/db/chats.py and the /chats routes (P7-T2)."""
import concurrent.futures
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.chat_routes import router as chat_router
from src.config import get_settings, reset_settings_singleton
from src.db import chats
from src.db.database import get_connection, run_migrations

OWNER = "owner"
MEMBER = "member-1"


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Isolated SQLite file with all migrations applied."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'cora.db'}")
    reset_settings_singleton()
    run_migrations()
    yield
    reset_settings_singleton()


@pytest.fixture
def member(db):
    """A second user row for cross-user checks."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (id, username, role) VALUES (?, ?, 'member')",
            (MEMBER, "member1"),
        )
        conn.commit()
    finally:
        conn.close()
    return MEMBER


@pytest.fixture
def client(db, monkeypatch):
    """TestClient with protection off (every request acts as the owner)."""
    monkeypatch.setattr(get_settings(), "ENABLE_API_KEY_PROTECTION", False)
    app = FastAPI()
    app.include_router(chat_router, prefix="/api")
    return TestClient(app)


def _response(answer: str) -> dict:
    return {"answer": answer, "confidence": 0.9, "sources": ["knowledge_base"]}


def _turn_rows(chat_id: str):
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT message_id, seq, user_text, response_json FROM chat_turns "
            "WHERE chat_id = ? ORDER BY seq",
            (chat_id,),
        ).fetchall()
    finally:
        conn.close()


class TestRecordTurn:
    def test_same_message_id_upserts_and_keeps_seq(self, db):
        """A retry writes one row, keeps its seq, and updates the response (A9)."""
        chats.record_turn(OWNER, "c1", "m1", "hello", _response("a1"))
        chats.record_turn(OWNER, "c1", "m1", "hello edited", _response("a2"))

        rows = _turn_rows("c1")
        assert len(rows) == 1
        assert rows[0]["seq"] == 1
        assert rows[0]["user_text"] == "hello edited"
        assert json.loads(rows[0]["response_json"])["answer"] == "a2"

    def test_seq_increments_per_message(self, db):
        for i in range(1, 4):
            chats.record_turn(OWNER, "c1", f"m{i}", f"q{i}", _response(f"a{i}"))
        assert [row["seq"] for row in _turn_rows("c1")] == [1, 2, 3]

    def test_concurrent_writes_get_unique_seqs(self, db):
        """Ten threads racing on one chat produce seq values 1..10 exactly."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futures = [
                pool.submit(
                    chats.record_turn,
                    OWNER,
                    "c1",
                    f"m{i}",
                    f"q{i}",
                    _response(f"a{i}"),
                )
                for i in range(10)
            ]
            for future in futures:
                future.result()

        assert sorted(row["seq"] for row in _turn_rows("c1")) == list(range(1, 11))

    def test_member_write_on_owner_chat_raises(self, db, member):
        """Another user's write to a chat raises ChatNotFound and changes nothing."""
        chats.record_turn(OWNER, "c1", "m1", "hello", _response("a1"))

        with pytest.raises(chats.ChatNotFound):
            chats.record_turn(member, "c1", "m2", "hijack", _response("evil"))

        chat = chats.get_chat(OWNER, "c1")
        assert [t["message_id"] for t in chat["turns"]] == ["m1"]
        assert chat["turns"][0]["response"]["answer"] == "a1"


class TestChatTitle:
    def test_title_30_chars_unchanged(self):
        text = "x" * 30
        assert chats.chat_title(text) == text

    def test_title_31_chars_truncated(self):
        assert chats.chat_title("y" * 31) == "y" * 30 + "..."

    def test_title_set_on_insert_only(self, db):
        """A later turn must not rewrite the title (B3)."""
        chats.record_turn(OWNER, "c1", "m1", "a" * 40, _response("a1"))
        chats.record_turn(OWNER, "c1", "m2", "something else", _response("a2"))
        assert chats.get_chat(OWNER, "c1")["title"] == "a" * 30 + "..."


class TestLoadHistory:
    def test_history_oldest_first(self, db):
        for i in range(1, 4):
            chats.record_turn(OWNER, "c1", f"m{i}", f"q{i}", _response(f"a{i}"))
        history = chats.load_history("c1", exclude_message_id="", max_messages=10)
        assert history == [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "q2"},
            {"role": "assistant", "content": "a2"},
            {"role": "user", "content": "q3"},
            {"role": "assistant", "content": "a3"},
        ]

    def test_history_capped_at_max_messages(self, db):
        for i in range(1, 6):
            chats.record_turn(OWNER, "c1", f"m{i}", f"q{i}", _response(f"a{i}"))
        history = chats.load_history("c1", exclude_message_id="", max_messages=4)
        # max_messages // 2 = 2 newest turns, oldest first
        assert history == [
            {"role": "user", "content": "q4"},
            {"role": "assistant", "content": "a4"},
            {"role": "user", "content": "q5"},
            {"role": "assistant", "content": "a5"},
        ]

    def test_history_excludes_message_id(self, db):
        """The in-flight retry's own turn is not part of its history."""
        chats.record_turn(OWNER, "c1", "m1", "q1", _response("a1"))
        chats.record_turn(OWNER, "c1", "m2", "q2", _response("a2"))
        history = chats.load_history("c1", exclude_message_id="m2", max_messages=10)
        assert history == [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
        ]


class TestListAndGet:
    def test_list_chats_follows_last_turn(self, db):
        chats.record_turn(OWNER, "a", "m1", "first", _response("x"))
        chats.record_turn(OWNER, "b", "m1", "second", _response("x"))

        # Pin timestamps: CURRENT_TIMESTAMP is second-granularity, so two
        # writes in one second would tie. 'b' is pinned as the most recent.
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE chats SET updated_at = '2020-01-01 00:00:00' WHERE id = 'a'"
            )
            conn.execute(
                "UPDATE chats SET updated_at = '2020-01-02 00:00:00' WHERE id = 'b'"
            )
            conn.commit()
        finally:
            conn.close()

        assert [c["id"] for c in chats.list_chats(OWNER)] == ["b", "a"]

        # A new turn bumps the chat to the top via updated_at = CURRENT_TIMESTAMP.
        chats.record_turn(OWNER, "a", "m2", "again", _response("y"))
        assert [c["id"] for c in chats.list_chats(OWNER)] == ["a", "b"]

    def test_get_chat_shape(self, db):
        chats.record_turn(OWNER, "c1", "m1", "hello", _response("a1"))
        chats.record_turn(OWNER, "c1", "m2", "next", _response("a2"))

        chat = chats.get_chat(OWNER, "c1")
        assert chat["id"] == "c1"
        assert isinstance(chat["title"], str)
        assert isinstance(chat["created_at"], str)
        assert isinstance(chat["updated_at"], str)
        assert [t["message_id"] for t in chat["turns"]] == ["m1", "m2"]
        turn = chat["turns"][0]
        assert turn["answer_id"] == "m1-answer"
        assert turn["user_text"] == "hello"
        assert turn["response"]["answer"] == "a1"
        assert isinstance(turn["created_at"], str)

    def test_get_chat_other_user_returns_none(self, db, member):
        chats.record_turn(OWNER, "c1", "m1", "hello", _response("a1"))
        assert chats.get_chat(member, "c1") is None

    def test_delete_chat(self, db):
        chats.record_turn(OWNER, "c1", "m1", "hello", _response("a1"))
        assert chats.delete_chat(OWNER, "c1") is True
        assert chats.get_chat(OWNER, "c1") is None
        assert _turn_rows("c1") == []

    def test_delete_chat_other_user_returns_false(self, db, member):
        chats.record_turn(OWNER, "c1", "m1", "hello", _response("a1"))
        assert chats.delete_chat(member, "c1") is False
        assert chats.get_chat(OWNER, "c1") is not None


class TestChatRoutes:
    def test_list_chats(self, db, client):
        chats.record_turn(OWNER, "c1", "m1", "hello", _response("a1"))
        response = client.get("/api/chats")
        assert response.status_code == 200
        body = response.json()
        assert [c["id"] for c in body["chats"]] == ["c1"]
        assert set(body["chats"][0]) == {"id", "title", "updated_at"}

    def test_get_chat(self, db, client):
        chats.record_turn(OWNER, "c1", "m1", "hello", _response("a1"))
        response = client.get("/api/chats/c1")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == "c1"
        assert body["turns"][0]["message_id"] == "m1"
        assert body["turns"][0]["answer_id"] == "m1-answer"

    def test_get_chat_not_found(self, db, client):
        assert client.get("/api/chats/nope").status_code == 404
        assert client.get("/api/chats/nope").json()["detail"] == "Chat not found"

    def test_delete_chat(self, db, client):
        chats.record_turn(OWNER, "c1", "m1", "hello", _response("a1"))
        assert client.delete("/api/chats/c1").status_code == 204
        assert client.get("/api/chats/c1").status_code == 404

    def test_delete_chat_not_found(self, db, client):
        assert client.delete("/api/chats/nope").status_code == 404

    @pytest.mark.parametrize("bad_id", ["bad_id", "x" * 65])
    def test_bad_chat_id_rejected(self, db, client, bad_id):
        """Underscores and >64 chars violate the conversation_id constraints."""
        assert client.get(f"/api/chats/{bad_id}").status_code == 422
        assert client.delete(f"/api/chats/{bad_id}").status_code == 422
