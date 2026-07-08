"""Tests for src/api/main.py endpoints and middleware behavior."""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def test_client():
    return TestClient(app)


class TestServeSpaPathTraversal:
    """Regression tests for the SPA fallback path-traversal protection.

    Note: TestClient/httpx normalizes literal '..' segments in the request path,
    so the real attack surface is URL-encoded traversal sequences. The route still
    checks literal '..' defensively, but only encoded forms are testable here.
    """

    def test_url_encoded_dotdot_segments_rejected(self, test_client):
        """URL-encoded '%2e%2e' variants must be rejected before os.path.join."""
        response = test_client.get("/%2e%2e/%2e%2e/%2e%2e/etc/passwd")
        assert response.status_code == 404

    def test_mixed_case_encoded_dotdot_rejected(self, test_client):
        response = test_client.get("/%2E%2e/%2E%2E/secret")
        assert response.status_code == 404

    def test_api_routes_not_served_by_spa_fallback(self, test_client):
        """Missed API routes must return 404, not the SPA index.html."""
        response = test_client.get("/v1/nonexistent")
        assert response.status_code == 404
        # It should not be a generic HTML fallback
        assert response.headers.get("content-type", "").startswith("application/json")
