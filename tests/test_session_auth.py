"""Tests for session-auth helpers and the /api/auth routes."""
import hashlib

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from loguru import logger

from src.api.auth import login_limiter
from src.api.auth.credentials import hash_password
from src.api.auth.session_auth import (
    SESSION_COOKIE,
    create_session,
    current_user_id,
    delete_session,
    delete_sessions,
    key_matches,
    session_user_id,
)
from src.api.middleware import register_exception_handlers
from src.api.middleware.security import SecurityMiddleware, generate_api_key
from src.api.session_routes import router as session_router
from src.config import get_settings, reset_settings_singleton
from src.db.database import get_connection, run_migrations
from src.db.users import OWNER_USER_ID

OWNER_USERNAME = "boss"
OWNER_PASSWORD = "owner-password-15"


@pytest.fixture(autouse=True)
def _reset_login_limiter():
    """Every test starts with an empty rate-limiter window."""
    login_limiter.reset()


@pytest.fixture
def api_key(tmp_path, monkeypatch) -> str:
    """Isolated SQLite DB (migrations applied) plus a configured API key."""
    key = generate_api_key()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'cora.db'}")
    monkeypatch.setenv("API_ACCESS_KEY", key)
    reset_settings_singleton()
    run_migrations()
    return key


@pytest.fixture
def protection_on(monkeypatch, api_key) -> str:
    """Enable API key protection; returns the configured key."""
    monkeypatch.setattr(get_settings(), "ENABLE_API_KEY_PROTECTION", True)
    return api_key


@pytest.fixture
def protected_app() -> FastAPI:
    """Minimal app with the real path lists, middleware, and session router."""
    from src.api.main import API_KEY_EXCLUDED_PATHS, API_KEY_PROTECTED_PATHS

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(session_router, prefix="/api")

    @app.get("/v1/health")
    def v1_health():
        return {"status": "ok"}

    @app.post("/v1/query")
    def v1_query():
        return {"ok": True}

    @app.get("/v1/whoami")
    def whoami(request: Request):
        return {"user_id": request.state.user_id}

    app.add_middleware(
        SecurityMiddleware,
        protected_paths=API_KEY_PROTECTED_PATHS,
        exclude_paths=API_KEY_EXCLUDED_PATHS,
    )
    return app


@pytest.fixture
def claimed_owner(protected_app, protection_on) -> TestClient:
    """Protection on + a claimed owner; returns a client holding the owner cookie."""
    client = TestClient(protected_app, base_url="https://testserver")
    response = client.post(
        "/api/auth/owner",
        json={
            "api_key": protection_on,
            "username": OWNER_USERNAME,
            "password": OWNER_PASSWORD,
        },
    )
    assert response.status_code == 204
    return client


def _insert_non_owner(username: str) -> str:
    """Insert a non-owner row directly — no API creates one any more, but a
    stale row exercises the owner-only guards."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (id, username, role, password_hash) "
            "VALUES (?, ?, 'member', ?)",
            (f"u-{username}", username, hash_password("stale-password-15")),
        )
        conn.commit()
    finally:
        conn.close()
    return f"u-{username}"


class TestKeyMatches:
    def test_matching_key(self, api_key):
        assert key_matches(api_key) is True

    def test_wrong_key(self, api_key):
        assert key_matches("wrong-key") is False

    def test_missing_provided(self, api_key):
        assert key_matches(None) is False
        assert key_matches("") is False

    def test_no_key_configured(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "API_ACCESS_KEY", None)
        assert key_matches("anything") is False


class TestSessionRows:
    def test_round_trip(self, api_key):
        assert session_user_id(create_session(OWNER_USER_ID)) == OWNER_USER_ID

    def test_unknown_token(self, api_key):
        assert session_user_id("not-a-session-token") is None

    def test_deleted_session(self, api_key):
        token = create_session(OWNER_USER_ID)
        delete_session(token)
        assert session_user_id(token) is None

    def test_expired_session(self, api_key):
        token = create_session(OWNER_USER_ID)
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE auth_sessions SET expires_at = datetime('now', '-1 second')"
            )
            conn.commit()
        finally:
            conn.close()
        assert session_user_id(token) is None

    def test_session_invalid_after_key_change(self, api_key, monkeypatch):
        """Key rotation invalidates every session via the key fingerprint."""
        token = create_session(OWNER_USER_ID)
        monkeypatch.setattr(get_settings(), "API_ACCESS_KEY", generate_api_key())
        assert session_user_id(token) is None

    def test_no_key_configured(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "API_ACCESS_KEY", None)
        assert key_matches("anything") is False
        assert session_user_id("anything") is None
        assert session_user_id(None) is None

    def test_table_stores_hash_not_raw_token(self, api_key):
        token = create_session(OWNER_USER_ID)
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT token_hash, user_id, key_fingerprint FROM auth_sessions"
            ).fetchall()
        finally:
            conn.close()
        assert len(rows) == 1
        # codeql[py/weak-sensitive-data-hashing] -- high-entropy tokens, not passwords
        expected_token_hash = hashlib.sha256(token.encode()).hexdigest()
        # codeql[py/weak-sensitive-data-hashing] -- high-entropy tokens, not passwords
        expected_fingerprint = hashlib.sha256(api_key.encode()).hexdigest()
        assert rows[0]["token_hash"] == expected_token_hash
        assert rows[0]["user_id"] == OWNER_USER_ID
        assert rows[0]["key_fingerprint"] == expected_fingerprint
        assert token not in dict(rows[0]).values()


class TestDeleteSessions:
    def test_keep_token_survives(self, api_key):
        uid = OWNER_USER_ID
        other_uid = _insert_non_owner("frank")
        t1 = create_session(uid)
        t2 = create_session(uid)
        other = create_session(other_uid)

        delete_sessions(uid, keep_token=t1)
        assert session_user_id(t1) == uid
        assert session_user_id(t2) is None
        assert session_user_id(other) == other_uid

        delete_sessions(uid)
        assert session_user_id(t1) is None


class TestCurrentUserId:
    def test_protection_off_returns_owner(self, api_key, monkeypatch):
        monkeypatch.setattr(get_settings(), "ENABLE_API_KEY_PROTECTION", False)
        request = Request({"type": "http"})
        assert current_user_id(request) == OWNER_USER_ID

    def test_protection_on_returns_state_user_id(self, api_key, monkeypatch):
        monkeypatch.setattr(get_settings(), "ENABLE_API_KEY_PROTECTION", True)
        request = Request({"type": "http"})
        request.state.user_id = OWNER_USER_ID
        assert current_user_id(request) == OWNER_USER_ID

    def test_protection_on_missing_state_raises(self, api_key, monkeypatch):
        """Fail closed: no owner fallback when the middleware never ran."""
        monkeypatch.setattr(get_settings(), "ENABLE_API_KEY_PROTECTION", True)
        request = Request({"type": "http"})
        with pytest.raises(AttributeError):
            current_user_id(request)


class TestSessionRoutesProtectionOff:
    """With protection off, the session routes report/return early."""

    def test_get_session_reports_owner(self, protected_app, api_key, monkeypatch):
        monkeypatch.setattr(get_settings(), "ENABLE_API_KEY_PROTECTION", False)
        client = TestClient(protected_app)
        response = client.get("/api/auth/session")
        assert response.status_code == 200
        assert response.json() == {
            "required": False,
            "authenticated": True,
            "owner_claim_required": False,
            "user": {"id": OWNER_USER_ID, "username": "owner", "role": "owner"},
        }

    @pytest.mark.parametrize(
        "path,body",
        [
            ("/api/auth/session", {"username": "alice", "password": "x"}),
            (
                "/api/auth/owner",
                {"api_key": "k", "username": "alice", "password": "a" * 15},
            ),
        ],
    )
    def test_post_not_available(self, protected_app, monkeypatch, path, body):
        monkeypatch.setattr(get_settings(), "ENABLE_API_KEY_PROTECTION", False)
        client = TestClient(protected_app)
        response = client.post(path, json=body)
        assert response.status_code == 404


class TestSessionRoutesProtectionOn:
    """With protection on, /api/auth is public but everything else needs auth."""

    def test_get_session_unauthenticated_unclaimed(self, protected_app, protection_on):
        """Unclaimed owner: the SPA must show the claim form."""
        client = TestClient(protected_app)
        response = client.get("/api/auth/session")
        assert response.status_code == 200
        assert response.json() == {
            "required": True,
            "authenticated": False,
            "owner_claim_required": True,
            "user": None,
        }

    def test_get_session_unauthenticated_claimed(self, claimed_owner):
        client = TestClient(claimed_owner.app)
        response = client.get("/api/auth/session")
        assert response.status_code == 200
        assert response.json() == {
            "required": True,
            "authenticated": False,
            "owner_claim_required": False,
            "user": None,
        }

    def test_get_session_with_cookie(self, claimed_owner):
        response = claimed_owner.get("/api/auth/session")
        assert response.status_code == 200
        assert response.json() == {
            "required": True,
            "authenticated": True,
            "owner_claim_required": False,
            "user": {"id": OWNER_USER_ID, "username": OWNER_USERNAME, "role": "owner"},
        }

    def test_get_session_with_api_key(self, protected_app, protection_on):
        client = TestClient(protected_app)
        response = client.get(
            "/api/auth/session", headers={"X-API-Key": protection_on}
        )
        assert response.status_code == 200
        assert response.json() == {
            "required": True,
            "authenticated": True,
            "owner_claim_required": True,
            "user": {"id": OWNER_USER_ID, "username": "owner", "role": "owner"},
        }

    def test_api_key_sets_owner_identity(self, protected_app, protection_on):
        """X-API-Key auth marks the request as the built-in owner."""
        client = TestClient(protected_app)
        response = client.get(
            "/v1/whoami", headers={"X-API-Key": protection_on}
        )
        assert response.status_code == 200
        assert response.json() == {"user_id": OWNER_USER_ID}

    def test_cookie_sets_session_identity(self, protected_app, protection_on):
        """Cookie auth marks the request with the session row's user_id."""
        client = TestClient(protected_app)
        client.cookies.set(SESSION_COOKIE, create_session(OWNER_USER_ID))
        response = client.get("/v1/whoami")
        assert response.status_code == 200
        assert response.json() == {"user_id": OWNER_USER_ID}

    def test_api_prefix_still_protected(self, protected_app, protection_on):
        """The /api/auth exclusion must not unprotect the rest of /api."""
        client = TestClient(protected_app)
        assert client.get("/api/cora-health").status_code == 401


class TestOwnerClaim:
    """POST /api/auth/owner — one-time owner account setup."""

    def test_unclaimed_owner_login_fails(self, protected_app, protection_on):
        """Before the claim, the owner row has no password — any login → 401."""
        client = TestClient(protected_app)
        response = client.post(
            "/api/auth/session",
            json={"username": "owner", "password": "any-password-1"},
        )
        assert response.status_code == 401
        assert "set-cookie" not in response.headers

    def test_claim_wrong_key(self, protected_app, protection_on):
        client = TestClient(protected_app)
        response = client.post(
            "/api/auth/owner",
            json={
                "api_key": "wrong-key",
                "username": OWNER_USERNAME,
                "password": OWNER_PASSWORD,
            },
        )
        assert response.status_code == 401
        assert "set-cookie" not in response.headers

    def test_claim_success_sets_cookie_and_username(
        self, protected_app, protection_on
    ):
        client = TestClient(protected_app, base_url="https://testserver")
        response = client.post(
            "/api/auth/owner",
            json={
                "api_key": protection_on,
                "username": OWNER_USERNAME,
                "password": OWNER_PASSWORD,
            },
        )
        assert response.status_code == 204
        assert "set-cookie" in response.headers
        # The claim cookie authenticates protected routes and reports the new username.
        assert client.get("/v1/health").status_code == 200
        session = client.get("/api/auth/session").json()
        assert session["user"]["username"] == OWNER_USERNAME
        assert session["user"]["role"] == "owner"
        assert session["owner_claim_required"] is False

    def test_second_claim_conflict(self, claimed_owner, protection_on):
        response = claimed_owner.post(
            "/api/auth/owner",
            json={
                "api_key": protection_on,
                "username": "someoneelse",
                "password": OWNER_PASSWORD,
            },
        )
        assert response.status_code == 409

    def test_claim_username_taken_by_stale_row(
        self, protected_app, protection_on
    ):
        _insert_non_owner("member1")
        client = TestClient(protected_app)
        response = client.post(
            "/api/auth/owner",
            json={
                "api_key": protection_on,
                "username": "member1",
                "password": OWNER_PASSWORD,
            },
        )
        assert response.status_code == 409


class TestLogin:
    """POST /api/auth/session — username/password login."""

    def test_wrong_password(self, claimed_owner):
        response = claimed_owner.post(
            "/api/auth/session",
            json={"username": OWNER_USERNAME, "password": "wrong-password!!"},
        )
        assert response.status_code == 401
        assert "set-cookie" not in response.headers

    def test_unknown_user_same_401_body(self, claimed_owner):
        client = TestClient(claimed_owner.app)
        unknown = client.post(
            "/api/auth/session",
            json={"username": "nosuchuser", "password": "whatever-pass!"},
        )
        wrong = client.post(
            "/api/auth/session",
            json={"username": OWNER_USERNAME, "password": "wrong-password!!"},
        )
        assert unknown.status_code == 401
        assert wrong.status_code == 401
        assert unknown.json() == wrong.json()

    def test_old_api_key_body_rejected(self, claimed_owner):
        """The old {api_key} body shape is gone (breaking change)."""
        response = claimed_owner.post("/api/auth/session", json={"api_key": "x"})
        assert response.status_code == 422

    @pytest.mark.parametrize("fetch_site", ["cross-site", "same-site"])
    def test_login_cross_site_rejected(
        self, claimed_owner, fetch_site
    ):
        """Login CSRF: a cross-site POST must not plant a session cookie."""
        response = claimed_owner.post(
            "/api/auth/session",
            json={"username": OWNER_USERNAME, "password": OWNER_PASSWORD},
            headers={"Sec-Fetch-Site": fetch_site},
        )
        assert response.status_code == 403
        assert "set-cookie" not in response.headers

    @pytest.mark.parametrize("fetch_site", ["cross-site", "same-site"])
    def test_claim_cross_site_rejected(
        self, protected_app, protection_on, fetch_site
    ):
        client = TestClient(protected_app)
        response = client.post(
            "/api/auth/owner",
            json={
                "api_key": protection_on,
                "username": OWNER_USERNAME,
                "password": OWNER_PASSWORD,
            },
            headers={"Sec-Fetch-Site": fetch_site},
        )
        assert response.status_code == 403
        assert "set-cookie" not in response.headers

    def test_login_same_origin_allowed(self, claimed_owner):
        response = claimed_owner.post(
            "/api/auth/session",
            json={"username": OWNER_USERNAME, "password": OWNER_PASSWORD},
            headers={"Sec-Fetch-Site": "same-origin"},
        )
        assert response.status_code == 204

    def test_login_success_sets_cookie(self, claimed_owner):
        client = TestClient(claimed_owner.app)
        response = client.post(
            "/api/auth/session",
            json={"username": OWNER_USERNAME, "password": OWNER_PASSWORD},
        )
        assert response.status_code == 204
        cookie = response.headers["set-cookie"]
        assert cookie.startswith(f"{SESSION_COOKIE}=")
        assert "HttpOnly" in cookie
        assert "SameSite=strict" in cookie
        assert "Path=/" in cookie
        assert "Max-Age=604800" in cookie
        assert "; Secure" in cookie

    def test_login_cookie_secure_flag_toggle(
        self, claimed_owner, monkeypatch
    ):
        """AUTH_COOKIE_SECURE=False omits the Secure attribute."""
        monkeypatch.setattr(get_settings(), "AUTH_COOKIE_SECURE", False)
        client = TestClient(claimed_owner.app)
        response = client.post(
            "/api/auth/session",
            json={"username": OWNER_USERNAME, "password": OWNER_PASSWORD},
        )
        assert response.status_code == 204
        assert "; Secure" not in response.headers["set-cookie"]

    def test_login_replaces_previous_cookie(self, claimed_owner):
        """A second sign-in rotates the session: the old token is dead."""
        first_token = claimed_owner.cookies.get(SESSION_COOKIE)

        assert claimed_owner.post(
            "/api/auth/session",
            json={"username": OWNER_USERNAME, "password": OWNER_PASSWORD},
        ).status_code == 204

        replay = TestClient(claimed_owner.app, base_url="https://testserver")
        replay.cookies.set(SESSION_COOKIE, first_token)
        assert replay.get("/v1/health").status_code == 401
        # The new session still authenticates.
        assert claimed_owner.get("/v1/health").status_code == 200


class TestLoginLimiter:
    """5 attempts/minute per (client IP, lowercased username)."""

    def test_other_ip_not_limited(self):
        """An attacker's budget is theirs alone: 5 fails from one IP leave
        the same username open from another."""
        for _ in range(5):
            login_limiter.require_attempt("login", "1.2.3.4:akra")
        with pytest.raises(HTTPException) as exc:
            login_limiter.require_attempt("login", "1.2.3.4:akra")
        assert exc.value.status_code == 429
        login_limiter.require_attempt("login", "5.6.7.8:akra")

    def test_sixth_attempt_429(self, protected_app, protection_on):
        client = TestClient(protected_app)
        statuses = [
            client.post(
                "/api/auth/session",
                json={"username": "alice", "password": "wrong-password!!"},
            ).status_code
            for _ in range(5)
        ]
        assert statuses == [401] * 5
        # Attempt 6 is rejected before the password is even checked.
        response = client.post(
            "/api/auth/session",
            json={"username": "alice", "password": "any-password-15!"},
        )
        assert response.status_code == 429
        assert response.headers["Retry-After"] == "60"

    def test_other_username_not_limited(self, protected_app, protection_on):
        """The limiter is per-username: 5 fails on one name leave others open."""
        client = TestClient(protected_app)
        for _ in range(5):
            client.post(
                "/api/auth/session",
                json={"username": "alice", "password": "wrong-password!!"},
            )
        # A different username gets a normal 401, not the 429.
        response = client.post(
            "/api/auth/session",
            json={"username": "otheruser", "password": "other-password-15"},
        )
        assert response.status_code == 401

    def test_case_shares_one_counter(self, protected_app, protection_on):
        """`Alice` and `alice` are the same account — one shared counter."""
        client = TestClient(protected_app)
        for _ in range(5):
            client.post(
                "/api/auth/session",
                json={"username": "Alice", "password": "wrong-password!!"},
            )
        response = client.post(
            "/api/auth/session",
            json={"username": "alice", "password": "any-password-15!"},
        )
        assert response.status_code == 429


class TestSessionCookies:
    """Cookie lifecycle against a signed-in owner."""

    def test_session_cookie_opens_protected_route(self, claimed_owner):
        assert claimed_owner.get("/v1/health").status_code == 200

    def test_cookie_rejected_after_key_rotation(
        self, claimed_owner, monkeypatch
    ):
        monkeypatch.setattr(get_settings(), "API_ACCESS_KEY", generate_api_key())
        assert claimed_owner.get("/v1/health").status_code == 401

    def test_delete_session_expires_cookie(self, claimed_owner):
        response = claimed_owner.delete("/api/auth/session")
        assert response.status_code == 204
        cookie = response.headers["set-cookie"]
        assert cookie.startswith(f"{SESSION_COOKIE}=")
        assert "Max-Age=0" in cookie or "Expires=Thu, 01 Jan 1970" in cookie
        assert claimed_owner.get("/v1/health").status_code == 401

    def test_saved_cookie_value_rejected_after_delete(self, claimed_owner):
        """DELETE removes the server-side row: a saved cookie no longer works."""
        token = claimed_owner.cookies.get(SESSION_COOKIE)
        assert claimed_owner.get("/v1/health").status_code == 200

        claimed_owner.delete("/api/auth/session")
        claimed_owner.cookies.set(SESSION_COOKIE, token)
        assert claimed_owner.get("/v1/health").status_code == 401


class TestHasherPool:
    """argon2 runs on a dedicated executor — a login flood gets 503s instead
    of starving the shared asyncio.to_thread pool."""

    def test_login_503_when_hasher_queue_full(
        self, protected_app, protection_on, monkeypatch
    ):
        from src.api.auth import credentials

        calls = []
        monkeypatch.setattr(
            credentials, "verify_password", lambda *a: calls.append(a)
        )
        for _ in range(credentials._HASH_QUEUE_LIMIT):
            assert credentials._hash_slots.acquire(blocking=False)
        try:
            response = TestClient(protected_app).post(
                "/api/auth/session",
                json={"username": "nobody", "password": "x" * 15},
            )
        finally:
            for _ in range(credentials._HASH_QUEUE_LIMIT):
                credentials._hash_slots.release()

        assert response.status_code == 503
        assert response.headers["Retry-After"] == "5"
        assert calls == []


class TestErrorHandlerHeaders:
    def test_custom_http_exception_headers_pass_through(self):
        """The exception handler must forward exc.headers to the response."""
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/boom")
        def boom():
            raise HTTPException(
                status_code=418, detail="teapot", headers={"X-Why": "tea"}
            )

        response = TestClient(app).get("/boom")
        assert response.status_code == 418
        assert response.headers["X-Why"] == "tea"


class TestLoginLogging:
    def test_failed_sign_in_logs_username_and_ip(self, protection_on):
        """Operators need a log line to point fail2ban at."""
        from src.api.main import app

        captured: list[str] = []
        sink_id = logger.add(
            captured.append, format="{message}", level="WARNING"
        )
        try:
            client = TestClient(app)
            for _ in range(5):
                client.post(
                    "/api/auth/session",
                    json={
                        "username": "nosuchuser",
                        "password": "never-logged-password",
                    },
                )
            assert client.post(
                "/api/auth/session",
                json={
                    "username": "nosuchuser",
                    "password": "never-logged-password",
                },
            ).status_code == 429
        finally:
            logger.remove(sink_id)

        logs = "".join(captured)
        assert "Failed sign-in for nosuchuser from testclient" in logs
        assert "Sign-in rate limited for nosuchuser from testclient" in logs
        assert "never-logged-password" not in logs

    def test_login_does_not_log_credentials(self, protection_on):
        """Submitted passwords and keys never reach the logs — 401, 422, 429.

        Runs against the real app so LoggingMiddleware and the production
        exception handlers are exercised.
        """
        from src.api.main import app

        password = "attempted-password-that-must-not-be-logged"
        wrong_key = "attempted-key-that-must-not-be-logged"
        captured: list[str] = []
        sink_id = logger.add(captured.append, format="{message}", level="DEBUG")
        try:
            client = TestClient(app)
            assert client.post(
                "/api/auth/session",
                json={"username": "nobody", "password": password},
            ).status_code == 401
            assert client.post(
                "/api/auth/session",
                json={"username": "!!", "password": password},
            ).status_code == 422
            for _ in range(5):
                client.post(
                    "/api/auth/session",
                    json={"username": "nobody", "password": password},
                )
            assert client.post(
                "/api/auth/session",
                json={"username": "nobody", "password": password},
            ).status_code == 429
            assert client.post(
                "/api/auth/owner",
                json={
                    "api_key": wrong_key,
                    "username": "boss",
                    "password": password + "!!",
                },
            ).status_code == 401
        finally:
            logger.remove(sink_id)

        logs = "".join(captured)
        assert password not in logs
        assert wrong_key not in logs
        assert protection_on not in logs


class TestRealAppRouting:
    def test_session_route_beats_spa_catch_all(self, api_key):
        """GET /api/auth/session resolves to the router, not the SPA 404."""
        from src.api.main import app

        response = TestClient(app).get("/api/auth/session")
        assert response.status_code == 200
        assert set(response.json()) == {
            "required",
            "authenticated",
            "owner_claim_required",
            "user",
        }
