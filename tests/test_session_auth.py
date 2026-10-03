"""Tests for session-auth helpers and the /api/auth/session routes (P3-T2/T3, P6-T1, P7-T1)."""
import hashlib

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from loguru import logger

from src.api.auth.session_auth import (
    OWNER_USER_ID,
    SESSION_COOKIE,
    create_session,
    current_user_id,
    delete_session,
    key_matches,
    session_user_id,
)
from src.api.middleware import register_exception_handlers
from src.api.middleware.security import SecurityMiddleware, generate_api_key
from src.api.session_routes import router as session_router
from src.config import get_settings, reset_settings_singleton
from src.db.database import get_connection, run_migrations


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
        assert rows[0]["token_hash"] == hashlib.sha256(token.encode()).hexdigest()
        assert rows[0]["user_id"] == OWNER_USER_ID
        assert rows[0]["key_fingerprint"] == hashlib.sha256(
            api_key.encode()
        ).hexdigest()
        assert token not in dict(rows[0]).values()


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

    def test_get_session_reports_not_required(self, protected_app, monkeypatch):
        monkeypatch.setattr(get_settings(), "ENABLE_API_KEY_PROTECTION", False)
        client = TestClient(protected_app)
        response = client.get("/api/auth/session")
        assert response.status_code == 200
        assert response.json() == {"required": False, "authenticated": True}

    def test_post_session_not_available(self, protected_app, monkeypatch):
        monkeypatch.setattr(get_settings(), "ENABLE_API_KEY_PROTECTION", False)
        client = TestClient(protected_app)
        response = client.post("/api/auth/session", json={"api_key": "any"})
        assert response.status_code == 404


class TestSessionRoutesProtectionOn:
    """With protection on, /api/auth is public but everything else needs auth."""

    def test_get_session_unauthenticated(self, protected_app, protection_on):
        client = TestClient(protected_app)
        response = client.get("/api/auth/session")
        assert response.status_code == 200
        assert response.json() == {"required": True, "authenticated": False}

    def test_get_session_with_cookie(self, protected_app, protection_on):
        client = TestClient(protected_app)
        client.cookies.set(SESSION_COOKIE, create_session(OWNER_USER_ID))
        response = client.get("/api/auth/session")
        assert response.status_code == 200
        assert response.json() == {"required": True, "authenticated": True}

    def test_get_session_with_api_key(self, protected_app, protection_on):
        client = TestClient(protected_app)
        response = client.get(
            "/api/auth/session", headers={"X-API-Key": protection_on}
        )
        assert response.status_code == 200
        assert response.json() == {"required": True, "authenticated": True}

    def test_api_key_sets_owner_identity(self, protected_app, protection_on):
        """X-API-Key auth marks the request as the built-in owner (D15/D31)."""
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

    def test_login_wrong_key(self, protected_app, protection_on):
        client = TestClient(protected_app)
        response = client.post("/api/auth/session", json={"api_key": "wrong"})
        assert response.status_code == 401
        assert "set-cookie" not in response.headers

    @pytest.mark.parametrize("fetch_site", ["cross-site", "same-site"])
    def test_login_cross_site_rejected(
        self, protected_app, protection_on, fetch_site
    ):
        """Login CSRF: a cross-site POST must not plant a session cookie, even
        with the correct access key."""
        client = TestClient(protected_app)
        response = client.post(
            "/api/auth/session",
            json={"api_key": protection_on},
            headers={"Sec-Fetch-Site": fetch_site},
        )
        assert response.status_code == 403
        assert "set-cookie" not in response.headers

    def test_login_same_origin_allowed(self, protected_app, protection_on):
        client = TestClient(protected_app)
        response = client.post(
            "/api/auth/session",
            json={"api_key": protection_on},
            headers={"Sec-Fetch-Site": "same-origin"},
        )
        assert response.status_code == 204

    def test_login_success_sets_cookie(self, protected_app, protection_on):
        client = TestClient(protected_app)
        response = client.post(
            "/api/auth/session", json={"api_key": protection_on}
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
        self, protected_app, protection_on, monkeypatch
    ):
        """AUTH_COOKIE_SECURE=False omits the Secure attribute."""
        monkeypatch.setattr(get_settings(), "AUTH_COOKIE_SECURE", False)
        client = TestClient(protected_app)
        response = client.post(
            "/api/auth/session", json={"api_key": protection_on}
        )
        assert response.status_code == 204
        assert "; Secure" not in response.headers["set-cookie"]

    def test_session_cookie_opens_protected_route(self, protected_app, protection_on):
        """The cookie from POST /auth/session authenticates /v1 requests."""
        client = TestClient(protected_app, base_url="https://testserver")
        assert client.post(
            "/api/auth/session", json={"api_key": protection_on}
        ).status_code == 204
        assert client.get("/v1/health").status_code == 200

    def test_cookie_rejected_after_key_rotation(
        self, protected_app, protection_on, monkeypatch
    ):
        client = TestClient(protected_app, base_url="https://testserver")
        client.post("/api/auth/session", json={"api_key": protection_on})
        assert client.get("/v1/health").status_code == 200

        monkeypatch.setattr(get_settings(), "API_ACCESS_KEY", generate_api_key())
        assert client.get("/v1/health").status_code == 401

    def test_delete_session_expires_cookie(self, protected_app, protection_on):
        client = TestClient(protected_app, base_url="https://testserver")
        client.post("/api/auth/session", json={"api_key": protection_on})
        assert client.get("/v1/health").status_code == 200

        response = client.delete("/api/auth/session")
        assert response.status_code == 204
        cookie = response.headers["set-cookie"]
        assert cookie.startswith(f"{SESSION_COOKIE}=")
        assert "Max-Age=0" in cookie or "Expires=Thu, 01 Jan 1970" in cookie
        assert client.get("/v1/health").status_code == 401

    def test_saved_cookie_value_rejected_after_delete(
        self, protected_app, protection_on
    ):
        """DELETE removes the server-side row: a saved cookie no longer works."""
        client = TestClient(protected_app, base_url="https://testserver")
        client.post("/api/auth/session", json={"api_key": protection_on})
        token = client.cookies.get(SESSION_COOKIE)
        assert client.get("/v1/health").status_code == 200

        client.delete("/api/auth/session")
        client.cookies.set(SESSION_COOKIE, token)
        assert client.get("/v1/health").status_code == 401

    def test_login_does_not_log_submitted_key(self, protection_on):
        """A submitted key never reaches the logs, for any login outcome.

        Runs against the real app so LoggingMiddleware and the production
        exception handlers are exercised.
        """
        from src.api.main import app

        wrong_key = "attempted-key-that-must-not-be-logged"
        oversized_key = "o" * 600
        captured: list[str] = []
        sink_id = logger.add(captured.append, format="{message}", level="DEBUG")
        try:
            client = TestClient(app)
            assert client.post(
                "/api/auth/session", json={"api_key": wrong_key}
            ).status_code == 401
            assert client.post(
                "/api/auth/session", json={"api_key": oversized_key}
            ).status_code == 422
            assert client.post(
                "/api/auth/session", json={"api_key": protection_on}
            ).status_code == 204
        finally:
            logger.remove(sink_id)

        logs = "".join(captured)
        assert wrong_key not in logs
        assert oversized_key not in logs
        assert protection_on not in logs


class TestInsecureTokenEndpoint:
    """POST /v1/auth/token issues JWTs for arbitrary user_ids — it must only
    exist when instance authentication gates the path first."""

    @pytest.fixture
    def token_app(self) -> FastAPI:
        from src.api.auth_routes import router as auth_router

        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(auth_router, prefix="/v1")
        return app

    def test_flag_on_protection_off_returns_404(self, token_app, monkeypatch):
        """The dangerous combo: flag on but no instance auth — any caller could
        mint a JWT for any user_id, so the endpoint refuses to exist."""
        settings = get_settings()
        monkeypatch.setattr(settings, "ENABLE_INSECURE_TOKEN_ENDPOINT", True)
        monkeypatch.setattr(settings, "ENABLE_API_KEY_PROTECTION", False)
        response = TestClient(token_app).post(
            "/v1/auth/token", json={"user_id": "victim"}
        )
        assert response.status_code == 404

    def test_flag_on_protection_on_issues_token(self, token_app, monkeypatch):
        """With protection on, only instance-credential holders reach the
        endpoint (enforced by SecurityMiddleware upstream); it then issues."""
        settings = get_settings()
        monkeypatch.setattr(settings, "ENABLE_INSECURE_TOKEN_ENDPOINT", True)
        monkeypatch.setattr(settings, "ENABLE_API_KEY_PROTECTION", True)
        monkeypatch.setattr(settings, "JWT_SECRET_KEY", "x" * 48)
        response = TestClient(token_app).post(
            "/v1/auth/token", json={"user_id": "u1"}
        )
        assert response.status_code == 200
        assert response.json()["access_token"]

    def test_flag_off_returns_404(self, token_app, monkeypatch):
        settings = get_settings()
        monkeypatch.setattr(settings, "ENABLE_INSECURE_TOKEN_ENDPOINT", False)
        monkeypatch.setattr(settings, "ENABLE_API_KEY_PROTECTION", True)
        response = TestClient(token_app).post(
            "/v1/auth/token", json={"user_id": "u1"}
        )
        assert response.status_code == 404


class TestRealAppRouting:
    def test_session_route_beats_spa_catch_all(self):
        """GET /api/auth/session resolves to the router, not the SPA 404."""
        from src.api.main import app

        response = TestClient(app).get("/api/auth/session")
        assert response.status_code == 200
        assert set(response.json()) == {"required", "authenticated"}
