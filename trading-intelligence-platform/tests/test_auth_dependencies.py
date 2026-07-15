"""Tests for src/auth/dependencies.py's get_current_user — called directly
as a plain function (it has no framework magic beyond its Depends()
defaults), same as every other dependency function tested in this suite.
"""

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.security import HTTPAuthorizationCredentials

from src.auth.dependencies import get_current_user
from src.auth.exceptions import AuthenticationError
from src.auth.jwt import create_access_token
from src.config import Settings
from src.db.models import User


def _settings() -> Settings:
    return Settings(SECRET_KEY="test-secret", DATABASE_URL="sqlite:///:memory:")


def _credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_missing_credentials_raises():
    with pytest.raises(AuthenticationError, match="Missing"):
        get_current_user(credentials=None, db=MagicMock(), settings=_settings())


def test_valid_token_resolves_the_user():
    settings = _settings()
    user_id = uuid.uuid4()
    token = create_access_token(str(user_id), settings)
    user = User(id=user_id, email="founder@local", hashed_password="x", is_active=True)
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = user

    result = get_current_user(credentials=_credentials(token), db=db, settings=settings)

    assert result is user


def test_unknown_user_id_raises():
    settings = _settings()
    token = create_access_token(str(uuid.uuid4()), settings)
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = None

    with pytest.raises(AuthenticationError, match="not found"):
        get_current_user(credentials=_credentials(token), db=db, settings=settings)


def test_inactive_user_raises():
    settings = _settings()
    user_id = uuid.uuid4()
    token = create_access_token(str(user_id), settings)
    user = User(id=user_id, email="founder@local", hashed_password="x", is_active=False)
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = user

    with pytest.raises(AuthenticationError, match="not found or inactive"):
        get_current_user(credentials=_credentials(token), db=db, settings=settings)


def test_malformed_subject_claim_raises():
    settings = _settings()
    token = create_access_token("not-a-uuid", settings)

    with pytest.raises(AuthenticationError, match="not a valid user id"):
        get_current_user(credentials=_credentials(token), db=MagicMock(), settings=settings)
