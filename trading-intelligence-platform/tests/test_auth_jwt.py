"""Tests for src/auth/jwt.py."""

import jwt as pyjwt
import pytest

from src.auth.exceptions import AuthenticationError
from src.auth.jwt import create_access_token, decode_access_token
from src.config import Settings

_USER_ID = "00000000-0000-0000-0000-000000000001"


def _settings(**overrides) -> Settings:
    base = {"SECRET_KEY": "test-secret", "DATABASE_URL": "sqlite:///:memory:"}
    base.update(overrides)
    return Settings(**base)


def test_round_trip_create_then_decode():
    token = create_access_token(_USER_ID, _settings())

    assert decode_access_token(token, _settings()) == _USER_ID


def test_expired_token_raises_authentication_error():
    # A negative expiry puts `exp` in the past immediately, no sleep needed.
    token = create_access_token(_USER_ID, _settings(ACCESS_TOKEN_EXPIRE_MINUTES=-1))

    with pytest.raises(AuthenticationError, match="expired"):
        decode_access_token(token, _settings())


def test_tampered_token_raises_authentication_error():
    token = create_access_token(_USER_ID, _settings())

    with pytest.raises(AuthenticationError, match="Invalid"):
        decode_access_token(token + "tampered", _settings())


def test_token_signed_with_a_different_secret_is_rejected():
    token = create_access_token(_USER_ID, _settings(SECRET_KEY="secret-a"))

    with pytest.raises(AuthenticationError, match="Invalid"):
        decode_access_token(token, _settings(SECRET_KEY="secret-b"))


def test_token_missing_subject_claim_is_rejected():
    # Crafted directly with pyjwt, bypassing create_access_token, to
    # simulate a token that's validly signed but malformed in content.
    settings = _settings()
    token = pyjwt.encode({"iat": 0, "exp": 9999999999}, settings.secret_key, algorithm=settings.jwt_algorithm)

    with pytest.raises(AuthenticationError, match="subject"):
        decode_access_token(token, settings)
