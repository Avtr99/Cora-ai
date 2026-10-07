import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from src.api.middleware.logging_middleware import LoggingMiddleware
from src.api.middleware.security import SecurityMiddleware, generate_api_key
from src.config import get_settings, reset_settings_singleton
from src.db.database import run_migrations


@pytest.fixture
def minimal_app() -> FastAPI:
    """Build a minimal FastAPI app for testing the security middleware."""
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/public")
    def public():
        return {"message": "public"}

    @app.get("/v1/private")
    def private():
        return {"message": "private"}

    @app.get("/v1/whoami")
    def whoami(request: Request):
        return {"user_id": request.state.user_id}

    @app.post("/query")
    def root_query():
        return {"message": "root query"}

    @app.post("/v1/query")
    def versioned_query():
        return {"message": "versioned query"}

    @app.post("/api/cora-query")
    def spa_query():
        return {"message": "SPA query"}

    return app


class TestSecurityHeaders:
    """Tests for security headers added by SecurityMiddleware."""

    def test_security_headers_present(self, minimal_app: FastAPI):
        """Middleware adds expected security headers to all responses."""
        app = minimal_app
        app.add_middleware(SecurityMiddleware)
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200
        headers = response.headers
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "Content-Security-Policy" in headers
        assert "Strict-Transport-Security" in headers


class TestAPIKeyProtection:
    """Tests for API key authentication in SecurityMiddleware."""

    def test_no_protection_when_no_protected_paths(self, minimal_app: FastAPI):
        """If protected_paths is None, no API key is required."""
        app = minimal_app
        app.add_middleware(SecurityMiddleware, protected_paths=None)
        client = TestClient(app)

        response = client.get("/v1/private")
        assert response.status_code == 200

    def test_missing_api_key_on_protected_path(self, minimal_app: FastAPI):
        """Protected path without API key returns 401."""
        app = minimal_app
        app.add_middleware(SecurityMiddleware, protected_paths=["/v1"])
        client = TestClient(app)

        response = client.get("/v1/private")
        assert response.status_code == 401
        assert response.json()["error"] == "unauthorized"

    @pytest.mark.parametrize("path", ["/query", "/v1/query", "/api/cora-query"])
    def test_all_query_prefixes_require_api_key(self, minimal_app: FastAPI, path: str):
        minimal_app.add_middleware(
            SecurityMiddleware,
            protected_paths=["/v1", "/api", "/query"],
        )

        response = TestClient(minimal_app).post(path)

        assert response.status_code == 401
        assert response.json()["error"] == "unauthorized"

    def test_invalid_api_key_on_protected_path(self, minimal_app: FastAPI):
        """Protected path with wrong API key returns 401."""
        app = minimal_app
        app.add_middleware(
            SecurityMiddleware,
            protected_paths=["/v1"],
        )
        client = TestClient(app)

        response = client.get("/v1/private", headers={"X-API-Key": "wrong-key"})
        assert response.status_code == 401

    def test_valid_api_key_on_protected_path(self, minimal_app: FastAPI, monkeypatch):
        """Protected path with correct API key returns 200."""
        api_key = generate_api_key()
        monkeypatch.setattr(get_settings(), "API_ACCESS_KEY", api_key)
        minimal_app.add_middleware(
            SecurityMiddleware,
            protected_paths=["/v1"],
        )

        response = TestClient(minimal_app).get(
            "/v1/private", headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200

    def test_valid_api_key_sets_owner_user_id(self, minimal_app: FastAPI, monkeypatch):
        """X-API-Key auth marks the request state as the built-in owner."""
        api_key = generate_api_key()
        monkeypatch.setattr(get_settings(), "API_ACCESS_KEY", api_key)
        minimal_app.add_middleware(
            SecurityMiddleware,
            protected_paths=["/v1"],
        )

        response = TestClient(minimal_app).get(
            "/v1/whoami", headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        assert response.json() == {"user_id": "owner"}

    def test_excluded_paths_bypass_api_key(self, minimal_app: FastAPI):
        """Excluded paths like /health bypass API key requirement."""
        app = minimal_app
        app.add_middleware(
            SecurityMiddleware,
            protected_paths=["/v1"],
            exclude_paths=["/health"]
        )
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200

    def test_public_path_not_protected(self, minimal_app: FastAPI):
        """Paths outside protected_paths do not require API key."""
        app = minimal_app
        app.add_middleware(SecurityMiddleware, protected_paths=["/v1"])
        client = TestClient(app)

        response = client.get("/public")
        assert response.status_code == 200

    def test_real_protected_and_excluded_lists(self):
        """/health stays public while /v1/health requires an API key.

        Uses the production path lists from src.api.main, proving that
        excluding "/health" does not exempt "/v1/health" (prefix matching is
        `path == excluded or path.startswith(excluded + "/")`).
        """
        from src.api.main import API_KEY_EXCLUDED_PATHS, API_KEY_PROTECTED_PATHS

        app = FastAPI()

        @app.get("/health")
        def health():
            return {"status": "ok"}

        @app.get("/v1/health")
        def v1_health():
            return {"status": "ok"}

        app.add_middleware(
            SecurityMiddleware,
            protected_paths=API_KEY_PROTECTED_PATHS,
            exclude_paths=API_KEY_EXCLUDED_PATHS,
        )
        client = TestClient(app)

        assert client.get("/health").status_code == 200
        response = client.get("/v1/health")
        assert response.status_code == 401
        assert response.json()["error"] == "unauthorized"


class TestSessionCookieAuth:
    """Cookie-based session auth and the Sec-Fetch-Site CSRF guard."""

    @pytest.fixture
    def api_key(self, tmp_path, monkeypatch) -> str:
        """Isolated SQLite DB (migrations applied) plus a configured API key."""
        key = generate_api_key()
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'cora.db'}")
        monkeypatch.setenv("API_ACCESS_KEY", key)
        reset_settings_singleton()
        run_migrations()
        return key

    @pytest.fixture
    def protected_client(self, minimal_app: FastAPI) -> TestClient:
        minimal_app.add_middleware(
            SecurityMiddleware,
            protected_paths=["/v1", "/api", "/query"],
        )
        return TestClient(minimal_app)

    def test_valid_session_cookie_on_get(
        self, protected_client: TestClient, api_key: str
    ):
        """A valid session cookie authenticates a GET on a protected path."""
        from src.api.auth.session_auth import SESSION_COOKIE, create_session
        from src.db.users import OWNER_USER_ID

        protected_client.cookies.set(SESSION_COOKIE, create_session(OWNER_USER_ID))
        response = protected_client.get("/v1/private")
        assert response.status_code == 200

    def test_session_cookie_post_cross_site_rejected(
        self, protected_client: TestClient, api_key: str
    ):
        """Cookie-authenticated unsafe method with cross-site fetch is forbidden."""
        from src.api.auth.session_auth import SESSION_COOKIE, create_session
        from src.db.users import OWNER_USER_ID

        protected_client.cookies.set(SESSION_COOKIE, create_session(OWNER_USER_ID))
        response = protected_client.post(
            "/v1/query", headers={"Sec-Fetch-Site": "cross-site"}
        )
        assert response.status_code == 403
        assert response.json()["error"] == "forbidden"

    def test_session_cookie_post_same_origin_allowed(
        self, protected_client: TestClient, api_key: str
    ):
        from src.api.auth.session_auth import SESSION_COOKIE, create_session
        from src.db.users import OWNER_USER_ID

        protected_client.cookies.set(SESSION_COOKIE, create_session(OWNER_USER_ID))
        response = protected_client.post(
            "/v1/query", headers={"Sec-Fetch-Site": "same-origin"}
        )
        assert response.status_code == 200

    def test_session_cookie_post_without_fetch_site_allowed(
        self, protected_client: TestClient, api_key: str
    ):
        """Requests without Sec-Fetch-Site (non-browser clients) are allowed."""
        from src.api.auth.session_auth import SESSION_COOKIE, create_session
        from src.db.users import OWNER_USER_ID

        protected_client.cookies.set(SESSION_COOKIE, create_session(OWNER_USER_ID))
        response = protected_client.post("/v1/query")
        assert response.status_code == 200

    def test_api_key_post_ignores_fetch_site(
        self, protected_client: TestClient, api_key: str
    ):
        """The CSRF check applies only to cookie auth, not X-API-Key."""
        response = protected_client.post(
            "/v1/query",
            headers={"X-API-Key": api_key, "Sec-Fetch-Site": "cross-site"},
        )
        assert response.status_code == 200

    def test_session_cookie_sets_session_user_id(
        self, protected_client: TestClient, api_key: str
    ):
        """Cookie auth marks the request state with the session row's user_id."""
        from src.api.auth.session_auth import SESSION_COOKIE, create_session
        from src.db.users import OWNER_USER_ID

        protected_client.cookies.set(SESSION_COOKIE, create_session(OWNER_USER_ID))
        response = protected_client.get("/v1/whoami")
        assert response.status_code == 200
        assert response.json() == {"user_id": OWNER_USER_ID}

    def test_invalid_session_cookie_rejected(
        self, protected_client: TestClient, api_key: str
    ):
        protected_client.cookies.set("cora_session", "not-a-real-token")
        response = protected_client.get("/v1/private")
        assert response.status_code == 401
        assert response.json()["error"] == "unauthorized"


class TestRequestIDValidation:
    def test_valid_client_request_id_is_preserved(self, minimal_app: FastAPI):
        minimal_app.add_middleware(LoggingMiddleware)
        response = TestClient(minimal_app).get(
            "/public", headers={"X-Request-ID": "client-request-123"}
        )

        assert response.headers["X-Request-ID"] == "client-request-123"

    @pytest.mark.parametrize("request_id", ["invalid request", "invalid!request", "x" * 65])
    def test_invalid_client_request_id_is_replaced(
        self, minimal_app: FastAPI, request_id: str
    ):
        minimal_app.add_middleware(LoggingMiddleware)
        response = TestClient(minimal_app).get(
            "/public", headers={"X-Request-ID": request_id}
        )

        generated = response.headers["X-Request-ID"]
        assert generated != request_id
        assert len(generated) == 8
        assert generated.replace("-", "").isalnum()


class TestGenerateAPIKey:
    """Tests for the API key generation helper."""

    def test_generate_api_key_length(self):
        """Generated API keys are 64 hex characters (32 bytes)."""
        key = generate_api_key()
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)

    def test_generate_api_keys_are_unique(self):
        """Generated API keys are unique."""
        keys = {generate_api_key() for _ in range(10)}
        assert len(keys) == 10
