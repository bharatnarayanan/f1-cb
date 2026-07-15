"""Tests for src/routes/auth.py — the one unprotected route (it's how a
request gets a token in the first place). Same dependency_overrides
pattern as every other route test file, minus overriding get_current_user
— there's nothing to override, this route doesn't require it.
"""

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.auth.password import hash_password
from src.config import Settings, get_settings
from src.db.models import User
from src.db.session import get_db
from src.main import app


def _fake_settings() -> Settings:
    return Settings(SECRET_KEY="test-secret", DATABASE_URL="sqlite:///:memory:")


def _user(password: str, is_active: bool = True) -> User:
    return User(
        id=uuid.uuid4(), email="founder@local", hashed_password=hash_password(password), is_active=is_active
    )


@pytest.fixture
def fake_db_session():
    return MagicMock()


@pytest.fixture
def client(fake_db_session):
    def _override_get_db():
        yield fake_db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = _fake_settings
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_login_with_correct_password_returns_a_token(client, fake_db_session):
    fake_db_session.execute.return_value.scalar_one_or_none.return_value = _user("correct-password")

    response = client.post("/api/v1/auth/login", json={"email": "founder@local", "password": "correct-password"})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 20


def test_login_with_wrong_password_is_rejected(client, fake_db_session):
    fake_db_session.execute.return_value.scalar_one_or_none.return_value = _user("correct-password")

    response = client.post("/api/v1/auth/login", json={"email": "founder@local", "password": "wrong-password"})

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_login_with_unknown_email_is_rejected(client, fake_db_session):
    fake_db_session.execute.return_value.scalar_one_or_none.return_value = None

    response = client.post("/api/v1/auth/login", json={"email": "nobody@local", "password": "anything"})

    assert response.status_code == 401


def test_login_for_an_inactive_user_is_rejected(client, fake_db_session):
    fake_db_session.execute.return_value.scalar_one_or_none.return_value = _user("correct-password", is_active=False)

    response = client.post("/api/v1/auth/login", json={"email": "founder@local", "password": "correct-password"})

    assert response.status_code == 401
