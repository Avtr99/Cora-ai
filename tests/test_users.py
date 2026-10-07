"""Tests for the user store (``src/db/users.py``) and credential
types/hashing (``src/api/auth/credentials.py``)."""
import threading
from unittest.mock import patch

import pytest
from pydantic import TypeAdapter, ValidationError

from src.api.auth import credentials
from src.api.auth.credentials import (
    Password,
    Username,
    hash_password,
    verify_password,
    verify_password_async,
)
from src.api.middleware.security import generate_api_key
from src.config import reset_settings_singleton
from src.db.database import get_connection, run_migrations
from src.db.users import (
    OWNER_USER_ID,
    UsernameTaken,
    claim_owner,
    get_password_hash,
    get_user,
    get_user_by_username,
    list_users,
    owner_claimed,
    set_password,
)


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Isolated SQLite DB with migrations applied and an API key configured."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'cora.db'}")
    monkeypatch.setenv("API_ACCESS_KEY", generate_api_key())
    reset_settings_singleton()
    run_migrations()


class TestPasswordHashing:
    def test_round_trip(self):
        hashed = hash_password("a-15-plus-char-password")
        assert verify_password("a-15-plus-char-password", hashed) is True

    def test_wrong_password(self):
        hashed = hash_password("a-15-plus-char-password")
        assert verify_password("a-different-password", hashed) is False

    def test_none_hash_runs_real_verify_and_returns_false(self):
        """Unknown user / unclaimed owner: a real argon2 verify still runs so
        response time does not reveal which accounts exist."""
        with patch.object(
            credentials._password_hasher,
            "verify",
            wraps=credentials._password_hasher.verify,
        ) as spy:
            assert verify_password("any-password", None) is False
            spy.assert_called_once()

    def test_nfkc_equivalent_password_verifies(self):
        """Compatibility characters normalize before hashing: "ﬁ" (U+FB01)
        and "fi" are the same password however the client encoded it."""
        hashed = hash_password("\ufb01" * 15)
        assert verify_password("fi" * 15, hashed) is True
        hashed = hash_password("fi" * 15)
        assert verify_password("\ufb01" * 15, hashed) is True


class TestAsyncHasher:
    async def test_verify_runs_on_argon2_worker(self, monkeypatch):
        names = []
        real_verify = credentials.verify_password

        def spy(password, password_hash):
            names.append(threading.current_thread().name)
            return real_verify(password, password_hash)

        monkeypatch.setattr(credentials, "verify_password", spy)
        assert await verify_password_async("any-password", None) is False
        assert names and all(n.startswith("argon2") for n in names)

    async def test_slot_released_after_hasher_error(self, monkeypatch):
        def boom(*_args):
            raise RuntimeError("argon2 exploded")

        monkeypatch.setattr(credentials, "verify_password", boom)
        with pytest.raises(RuntimeError):
            await verify_password_async("pw", "hash")

        for _ in range(credentials._HASH_QUEUE_LIMIT):
            assert credentials._hash_slots.acquire(blocking=False)
        for _ in range(credentials._HASH_QUEUE_LIMIT):
            credentials._hash_slots.release()


class TestCredentialTypes:
    def test_username_normalized(self):
        assert TypeAdapter(Username).validate_python("  Alice ") == "alice"

    @pytest.mark.parametrize("value", ["ab", "-abc", "a b", "a" * 33])
    def test_username_rejected(self, value):
        with pytest.raises(ValidationError):
            TypeAdapter(Username).validate_python(value)

    def test_password_bounds(self):
        adapter = TypeAdapter(Password)
        with pytest.raises(ValidationError):
            adapter.validate_python("a" * 14)
        assert adapter.validate_python("ab" * 8) == "ab" * 8
        with pytest.raises(ValidationError):
            adapter.validate_python("a" * 129)

    def test_password_one_repeated_char_rejected(self):
        adapter = TypeAdapter(Password)
        with pytest.raises(ValidationError, match="repeated character"):
            adapter.validate_python("a" * 15)
        with pytest.raises(ValidationError, match="repeated character"):
            adapter.validate_python("9" * 40)


class TestOwnerClaim:
    def test_claim_lifecycle(self, db):
        assert owner_claimed() is False
        assert claim_owner("alice", "hash-alice") is True
        assert owner_claimed() is True
        assert get_user(OWNER_USER_ID) == {
            "id": OWNER_USER_ID,
            "username": "alice",
            "role": "owner",
            "has_password": True,
        }
        # Second claim: row already has a password — no update.
        assert claim_owner("alice2", "hash-other") is False
        assert get_user(OWNER_USER_ID)["username"] == "alice"

    def test_claim_owner_username_taken_raises(self, db):
        """The username UNIQUE constraint still guards a collision — a
        leftover non-owner row holding the name turns into UsernameTaken."""
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO users (id, username, role, password_hash) "
                "VALUES ('stale', 'bob', 'member', 'hash-bob')"
            )
            conn.commit()
        finally:
            conn.close()
        with pytest.raises(UsernameTaken):
            claim_owner("bob", "hash-alice")


class TestUserStore:
    def test_list_users_has_no_password_hash(self, db):
        claim_owner("alice", "hash-alice")
        rows = list_users()
        assert [r["username"] for r in rows] == ["alice"]
        assert rows[0]["id"] == OWNER_USER_ID
        assert set(rows[0]) == {"id", "username", "role", "created_at"}

    def test_get_user_by_username_returns_hash_for_login(self, db):
        claim_owner("carol", "hash-carol")
        row = get_user_by_username("carol")
        assert row["password_hash"] == "hash-carol"
        assert row["role"] == "owner"
        assert get_user_by_username("nobody") is None

    def test_get_password_hash_by_id(self, db):
        assert get_password_hash(OWNER_USER_ID) is None  # unclaimed owner
        claim_owner("carol", "hash-carol")
        assert get_password_hash(OWNER_USER_ID) == "hash-carol"
        assert get_password_hash("nobody") is None  # unknown user

    def test_set_password(self, db):
        assert set_password(OWNER_USER_ID, "hash-new") is True
        assert get_user_by_username("owner")["password_hash"] == "hash-new"
        assert set_password("no-such-user", "hash") is False
