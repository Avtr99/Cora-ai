import os

# Set mock environment variables BEFORE importing modules that require Settings
if not os.environ.get("JWT_SECRET_KEY"):
    os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-for-ci-testing"

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from src.api.auth.token_utils import (
    JWTError,
    create_access_token,
    decode_access_token,
)


class TestCreateAccessToken:
    """Tests for JWT access token creation."""

    def test_create_token_success(self):
        """A valid user_id produces a non-empty JWT token."""
        token = create_access_token(user_id="user-123")
        assert isinstance(token, str)
        assert token.count(".") == 2  # JWT structure: header.payload.signature

    def test_create_token_with_additional_claims(self):
        """Additional claims are included in the token payload."""
        token = create_access_token(
            user_id="user-123",
            additional_claims={"role": "admin", "tenant": "acme"}
        )
        payload = decode_access_token(token)
        assert payload["user_id"] == "user-123"
        assert payload["role"] == "admin"
        assert payload["tenant"] == "acme"

    def test_create_token_rejects_protected_claims(self):
        """Protected claims like 'sub' are ignored rather than overridden."""
        token = create_access_token(
            user_id="user-123",
            additional_claims={"sub": "attacker", "role": "admin"}
        )
        payload = decode_access_token(token)
        assert payload["user_id"] == "user-123"  # original sub preserved
        assert payload["role"] == "admin"

    def test_create_token_rejects_invalid_user_id(self):
        """Non-string or empty user_ids raise JWTError."""
        with pytest.raises(JWTError):
            create_access_token(user_id="")

        with pytest.raises(JWTError):
            create_access_token(user_id=123)  # type: ignore[arg-type]

    def test_create_token_rejects_long_user_id(self):
        """User IDs longer than 256 characters are rejected."""
        with pytest.raises(JWTError):
            create_access_token(user_id="x" * 257)

    def test_create_token_custom_expiry(self):
        """Custom expiry delta is honored in the token payload."""
        token = create_access_token(
            user_id="user-123",
            expires_delta=timedelta(minutes=5)
        )
        payload = decode_access_token(token)
        # Token should expire roughly 5 minutes after issue
        iat = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        assert timedelta(minutes=4, seconds=50) < (exp - iat) <= timedelta(minutes=5, seconds=10)


class TestDecodeAccessToken:
    """Tests for JWT access token decoding and validation."""

    def test_decode_valid_token(self):
        """A valid token decodes to the expected user_id."""
        token = create_access_token(user_id="user-123")
        payload = decode_access_token(token)
        assert payload["user_id"] == "user-123"
        assert "exp" in payload
        assert "iat" in payload

    def test_decode_expired_token(self):
        """An expired token raises JWTError with code JWT_EXPIRED."""
        token = create_access_token(
            user_id="user-123",
            expires_delta=timedelta(seconds=-1)
        )
        with pytest.raises(JWTError) as exc_info:
            decode_access_token(token)
        assert exc_info.value.error_code == "JWT_EXPIRED"

    def test_decode_invalid_signature(self):
        """A token signed with a different secret is rejected."""
        token = create_access_token(user_id="user-123")
        with patch("src.api.auth.token_utils.get_settings") as mock_settings:
            mock_settings.return_value.JWT_SECRET_KEY = "different-secret-key-that-is-32-bytes"
            mock_settings.return_value.JWT_ALGORITHM = "HS256"
            with pytest.raises(JWTError) as exc_info:
                decode_access_token(token)
            assert exc_info.value.error_code == "JWT_INVALID"

    def test_decode_malformed_token(self):
        """A malformed token raises JWTError."""
        with pytest.raises(JWTError) as exc_info:
            decode_access_token("not-a-jwt")
        assert exc_info.value.error_code == "JWT_INVALID"

    def test_decode_wrong_token_type(self):
        """A token with wrong 'type' claim is rejected."""
        import jwt
        from src.config import get_settings

        settings = get_settings()
        payload = {
            "sub": "user-123",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
            "type": "refresh"
        }
        token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")
        with pytest.raises(JWTError) as exc_info:
            decode_access_token(token)
        assert exc_info.value.error_code == "JWT_INVALID_TYPE"


class TestJWTSecretKeyValidation:
    """Tests for JWT_SECRET_KEY configuration validation."""

    def test_missing_secret_key_raises_config_error(self):
        """Missing JWT_SECRET_KEY raises JWT_CONFIG_ERROR."""
        with patch("src.api.auth.token_utils.get_settings") as mock_settings:
            mock_settings.return_value.JWT_SECRET_KEY = None
            mock_settings.return_value.JWT_ALGORITHM = "HS256"
            mock_settings.return_value.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60
            with pytest.raises(JWTError) as exc_info:
                create_access_token(user_id="user-123")
            assert exc_info.value.error_code == "JWT_CONFIG_ERROR"

    def test_short_secret_key_raises_config_error(self):
        """JWT_SECRET_KEY shorter than 32 bytes raises JWT_CONFIG_ERROR."""
        with patch("src.api.auth.token_utils.get_settings") as mock_settings:
            mock_settings.return_value.JWT_SECRET_KEY = "short-secret"
            mock_settings.return_value.JWT_ALGORITHM = "HS256"
            mock_settings.return_value.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60
            with pytest.raises(JWTError) as exc_info:
                create_access_token(user_id="user-123")
            assert exc_info.value.error_code == "JWT_CONFIG_ERROR"
            assert "32 bytes" in exc_info.value.message

    def test_exactly_32_byte_secret_key_is_accepted(self):
        """A 32-byte secret key is accepted."""
        with patch("src.api.auth.token_utils.get_settings") as mock_settings:
            mock_settings.return_value.JWT_SECRET_KEY = "x" * 32
            mock_settings.return_value.JWT_ALGORITHM = "HS256"
            mock_settings.return_value.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60
            token = create_access_token(user_id="user-123")
            assert isinstance(token, str)
