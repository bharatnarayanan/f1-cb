"""Tests for src/routes/journal.py — route wiring only."""

import uuid
from unittest.mock import MagicMock

import fakeredis
import pytest
from fastapi.testclient import TestClient

from src.auth.dependencies import get_current_user
from src.cache.redis_client import RedisCache, get_redis_cache
from src.config import Settings, get_settings
from src.db.models import TradeJournalEntry, User
from src.db.session import get_db
from src.main import app
from src.market_data.factory import get_market_data_client

_FOUNDER_ID = uuid.uuid4()


def _fake_settings() -> Settings:
    return Settings(SECRET_KEY="test-secret", DATABASE_URL="sqlite:///:memory:", DATA_MODE="sample")


def _founder() -> User:
    return User(id=_FOUNDER_ID, email="founder@local", hashed_password="x", display_name="Founder")


@pytest.fixture
def fake_db_session():
    session = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = _founder()
    session.execute.return_value.scalars.return_value.all.return_value = [
        TradeJournalEntry(id=uuid.uuid4(), recommendation_id=None, user_id=_FOUNDER_ID, outcome="win", realized_pnl_pct=5.0)
    ]
    return session


@pytest.fixture
def client(fake_db_session):
    def _override_get_db():
        yield fake_db_session

    shared_cache = RedisCache(fakeredis.FakeRedis(decode_responses=True))
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis_cache] = lambda: shared_cache
    app.dependency_overrides[get_settings] = _fake_settings
    app.dependency_overrides[get_market_data_client] = lambda: MagicMock()
    app.dependency_overrides[get_current_user] = _founder
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_log_outcome(client, fake_db_session):
    response = client.post("/api/v1/journal", json={"outcome": "win", "realized_pnl_pct": 5.0, "observation": "clean breakout"})

    assert response.status_code == 200
    assert response.json()["outcome"] == "win"
    assert fake_db_session.commit.called


def test_log_outcome_rejects_unsupported_outcome(client):
    response = client.post("/api/v1/journal", json={"outcome": "meh"})

    assert response.status_code == 400


def test_list_entries(client):
    response = client.get("/api/v1/journal")

    assert response.status_code == 200
    assert response.json()["entries"][0]["outcome"] == "win"


def test_get_factor_weights(client, monkeypatch):
    monkeypatch.setattr("src.routes.journal.get_confidence_weights", lambda db: {"macro_sr_alignment": 0.3})

    response = client.get("/api/v1/journal/factor-weights")

    assert response.status_code == 200
    assert response.json()["weights"] == {"macro_sr_alignment": 0.3}


def test_recompute_weights(client, monkeypatch):
    fake_summary = {"macro_sr_alignment": {"before_weight": 0.25, "after_weight": 0.3, "alpha": 8, "beta": 5, "num_outcomes": 3}}
    monkeypatch.setattr("src.routes.journal.recompute_factor_weights", lambda db: fake_summary)

    response = client.post("/api/v1/journal/recompute-weights")

    assert response.status_code == 200
    assert response.json()["result"] == fake_summary
