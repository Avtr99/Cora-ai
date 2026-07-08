import os

# Set mock environment variables BEFORE importing modules that require Settings
if not os.environ.get("SECRET_KEY"):
    os.environ["SECRET_KEY"] = "test-secret-key-for-ci-testing"
if not os.environ.get("JWT_SECRET_KEY"):
    os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-for-ci-testing"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

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
