"""Tests for the user recovery CLI."""
import pytest

from src.api.auth.credentials import hash_password, verify_password
from src.cli.users import main
from src.db.database import run_migrations
from src.db.users import OWNER_USER_ID, claim_owner, get_user_by_username, owner_claimed
from src.api.auth.session_auth import create_session


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Isolated SQLite DB with migrations applied."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'cora.db'}")
    from src.config import reset_settings_singleton

    reset_settings_singleton()
    run_migrations()
    return tmp_path


def _getpass(values):
    iterator = iter(values)
    return lambda *_args, **_kwargs: next(iterator)


class TestList:
    def test_lists_users(self, db, capsys):
        claim_owner("member1", hash_password("member-password-15"))
        assert main(["list"]) == 0
        out = capsys.readouterr().out
        assert "owner" in out
        assert "member1" in out


class TestResetPassword:
    def test_reset_verifies_and_ends_sessions(self, db, monkeypatch):
        claim_owner("member1", hash_password("member-password-15"))
        create_session(OWNER_USER_ID)
        monkeypatch.setattr(
            "src.cli.users.getpass.getpass",
            _getpass(["brand-new-password!", "brand-new-password!"]),
        )
        assert main(["reset-password", "member1"]) == 0
        assert verify_password(
            "brand-new-password!",
            get_user_by_username("member1")["password_hash"],
        )
        # The old session row was deleted.
        from src.db.database import get_connection

        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT COUNT(*) FROM auth_sessions WHERE user_id = ?",
                (OWNER_USER_ID,),
            ).fetchone()
            assert rows[0] == 0
        finally:
            conn.close()

    def test_username_case_normalized(self, db, monkeypatch):
        """`reset-password Alice` finds the row stored as `alice`."""
        claim_owner("alice", hash_password("member-password-15"))
        monkeypatch.setattr(
            "src.cli.users.getpass.getpass",
            _getpass(["brand-new-password!", "brand-new-password!"]),
        )
        assert main(["reset-password", "Alice"]) == 0
        assert verify_password(
            "brand-new-password!",
            get_user_by_username("alice")["password_hash"],
        )

    def test_unknown_user_exit_1(self, db, monkeypatch):
        monkeypatch.setattr(
            "src.cli.users.getpass.getpass",
            _getpass(["brand-new-password!", "brand-new-password!"]),
        )
        assert main(["reset-password", "ghost"]) == 1

    def test_invalid_username_exit_1(self, db, capsys):
        """A name that cannot be a username reports 'Unknown user', exit 1."""
        assert main(["reset-password", "!!"]) == 1
        assert "Unknown user: !!" in capsys.readouterr().err

    def test_mismatch_exit_2(self, db, monkeypatch):
        claim_owner("member1", hash_password("member-password-15"))
        monkeypatch.setattr(
            "src.cli.users.getpass.getpass",
            _getpass(["brand-new-password!", "different-password!"]),
        )
        assert main(["reset-password", "member1"]) == 2

    def test_short_password_exit_2(self, db, monkeypatch):
        claim_owner("member1", hash_password("member-password-15"))
        monkeypatch.setattr(
            "src.cli.users.getpass.getpass", _getpass(["short", "short"])
        )
        assert main(["reset-password", "member1"]) == 2

    def test_fourteen_chars_exit_2(self, db, monkeypatch):
        claim_owner("member1", hash_password("member-password-15"))
        monkeypatch.setattr(
            "src.cli.users.getpass.getpass", _getpass(["a" * 14, "a" * 14])
        )
        assert main(["reset-password", "member1"]) == 2

    def test_reset_unclaimed_owner_claims(self, db, monkeypatch):
        """Recovery before the claim: set_password makes owner_claimed() true."""
        assert not owner_claimed()
        monkeypatch.setattr(
            "src.cli.users.getpass.getpass",
            _getpass(["brand-new-password!", "brand-new-password!"]),
        )
        assert main(["reset-password", "owner"]) == 0
        assert owner_claimed()
        assert verify_password(
            "brand-new-password!", get_user_by_username("owner")["password_hash"]
        )
