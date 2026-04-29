"""Tests for JWT authentication utilities (app.utils.auth)."""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from unittest.mock import MagicMock, patch

import jwt as pyjwt
import pytest
from fastapi import HTTPException

from app.utils import auth


@pytest.fixture(autouse=True)
def _reset_jwks_client():
    """Reset the module-level JWKS singleton between tests."""
    auth._jwks_client = None
    yield
    auth._jwks_client = None


SAMPLE_PAYLOAD = {
    "preferred_username": "testuser",
    "name": "Test User",
    "email": "test@example.com",
    "iss": "https://keycloak.example.com/realms/test",
    "exp": 9999999999,
}


def _make_request(auth_header: str | None = None):
    mock = MagicMock()
    mock.headers = {}
    if auth_header is not None:
        mock.headers["authorization"] = auth_header
    return mock


class TestDecodeJwt:
    @patch.object(auth, "OIDC_ISSUER_URL", "https://keycloak.example.com/realms/test")
    @patch.object(auth, "_jwks_client")
    def test_valid_token(self, mock_client):
        mock_key = MagicMock()
        mock_client.get_signing_key_from_jwt.return_value = mock_key

        with patch("jwt.decode", return_value=SAMPLE_PAYLOAD) as mock_decode:
            result = auth.decode_jwt("some.jwt.token")
            assert result["preferred_username"] == "testuser"
            mock_decode.assert_called_once()

    @patch.object(auth, "OIDC_ISSUER_URL", "")
    def test_no_issuer_raises_runtime_error(self):
        with pytest.raises(RuntimeError, match="OIDC_ISSUER_URL is not configured"):
            auth.decode_jwt("some.jwt.token")


class TestGetUserFromToken:
    @patch.object(auth, "decode_jwt", return_value=SAMPLE_PAYLOAD)
    def test_valid_bearer_token(self, _mock):
        request = _make_request("Bearer some.jwt.token")
        result = auth.get_user_from_token(request)
        assert result["preferred_username"] == "testuser"

    def test_no_auth_header(self):
        request = _make_request()
        assert auth.get_user_from_token(request) is None

    def test_non_bearer_header(self):
        request = _make_request("Basic dXNlcjpwYXNz")
        assert auth.get_user_from_token(request) is None

    @patch.object(auth, "decode_jwt", side_effect=pyjwt.ExpiredSignatureError)
    def test_expired_token_returns_none(self, _mock):
        request = _make_request("Bearer expired.token")
        assert auth.get_user_from_token(request) is None

    @patch.object(auth, "decode_jwt", side_effect=pyjwt.InvalidTokenError("bad"))
    def test_invalid_token_returns_none(self, _mock):
        request = _make_request("Bearer invalid.token")
        assert auth.get_user_from_token(request) is None


class TestRequireJwtUser:
    @pytest.mark.asyncio
    @patch.object(auth, "OIDC_ISSUER_URL", "")
    async def test_no_oidc_returns_503(self):
        request = _make_request("Bearer some.token")
        with pytest.raises(HTTPException) as exc_info:
            await auth.require_jwt_user(request)
        assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    @patch.object(auth, "OIDC_ISSUER_URL", "https://kc.example.com/realms/test")
    async def test_missing_bearer_returns_401(self):
        request = _make_request()
        with pytest.raises(HTTPException) as exc_info:
            await auth.require_jwt_user(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    @patch.object(auth, "OIDC_ISSUER_URL", "https://kc.example.com/realms/test")
    @patch.object(auth, "decode_jwt", side_effect=pyjwt.ExpiredSignatureError)
    async def test_expired_token_returns_401(self, _mock):
        request = _make_request("Bearer expired.token")
        with pytest.raises(HTTPException) as exc_info:
            await auth.require_jwt_user(request)
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    @patch.object(auth, "OIDC_ISSUER_URL", "https://kc.example.com/realms/test")
    @patch.object(auth, "decode_jwt", return_value={"iss": "x"})
    async def test_missing_username_returns_401(self, _mock):
        request = _make_request("Bearer valid.but.no.username")
        with pytest.raises(HTTPException) as exc_info:
            await auth.require_jwt_user(request)
        assert exc_info.value.status_code == 401
        assert "preferred_username" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch.object(auth, "OIDC_ISSUER_URL", "https://kc.example.com/realms/test")
    @patch.object(auth, "decode_jwt", return_value=SAMPLE_PAYLOAD)
    async def test_valid_token_returns_payload(self, _mock):
        request = _make_request("Bearer valid.token")
        result = await auth.require_jwt_user(request)
        assert result["preferred_username"] == "testuser"
