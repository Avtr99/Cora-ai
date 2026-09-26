import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.middleware.logging_middleware import LoggingMiddleware
from src.api.middleware.security import SecurityMiddleware, generate_api_key
from src.config import get_settings


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
        import src.api.middleware.security as security_module

        api_key = generate_api_key()
        app = minimal_app
        app.add_middleware(
            SecurityMiddleware,
            protected_paths=["/v1"],
        )

        # Inject the configured API key via Settings and temporarily override loader
        settings = get_settings()
        original_key = getattr(settings, "API_ACCESS_KEY", None)
        settings.API_ACCESS_KEY = api_key
        original_loader = security_module.SecurityMiddleware._load_api_keys
        monkeypatch.setattr(
            security_module.SecurityMiddleware,
            "_load_api_keys",
            lambda self: {self._hash_key(api_key)}
        )

        client = TestClient(app)
        response = client.get("/v1/private", headers={"X-API-Key": api_key})
        assert response.status_code == 200

        # Restore
        settings.API_ACCESS_KEY = original_key
        monkeypatch.setattr(
            security_module.SecurityMiddleware,
            "_load_api_keys",
            original_loader
        )

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
