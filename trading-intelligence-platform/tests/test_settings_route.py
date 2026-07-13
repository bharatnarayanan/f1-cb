"""Tests for src/routes/settings.py (Phase 7 Pass 2b) — route wiring only."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import fakeredis
import pytest
from fastapi.testclient import TestClient

from src.cache.redis_client import RedisCache, get_redis_cache
from src.config import Settings, get_settings
from src.db.models import RiskSettings, SectorIndexRecord, User, WatchlistConstituent
from src.db.session import get_db
from src.main import app
from src.market_data.factory import get_market_data_client

_FOUNDER_ID = uuid.uuid4()


def _fake_settings(**overrides) -> Settings:
    defaults = {"SECRET_KEY": "test-secret", "DATABASE_URL": "sqlite:///:memory:", "DATA_MODE": "sample"}
    defaults.update(overrides)
    return Settings(**defaults)


def _founder() -> User:
    return User(id=_FOUNDER_ID, email="founder@local", hashed_password="x")


def _risk_row() -> RiskSettings:
    return RiskSettings(
        user_id=_FOUNDER_ID, vix_normal_max=15.0, vix_elevated_max=20.0, vix_high_max=30.0,
        suppress_tactical_on_extreme=True, expiry_day_dampening=True, max_daily_recommendations=20,
        execution_mode="paper", updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def fake_db_session():
    session = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = _founder()
    session.execute.return_value.scalars.return_value.all.return_value = []
    return session


@pytest.fixture
def client(fake_db_session):
    def _override_get_db():
        yield fake_db_session

    shared_cache = RedisCache(fakeredis.FakeRedis(decode_responses=True))
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis_cache] = lambda: shared_cache
    # A zero-arg lambda, not `_fake_settings` directly: FastAPI introspects
    # whatever callable sits in dependency_overrides (even though it's
    # meant to just be invoked), and `_fake_settings(**overrides)`'s
    # **kwargs signature gets misread as a required "overrides" query
    # param, breaking every route with a 422 — a real bug caught live.
    app.dependency_overrides[get_settings] = lambda: _fake_settings()
    app.dependency_overrides[get_market_data_client] = lambda: MagicMock()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_get_watchlist(client, fake_db_session):
    fake_db_session.execute.return_value.scalars.return_value.all.side_effect = [
        [WatchlistConstituent(symbol="RELIANCE", display_name="Reliance", sector="Energy", is_active=True)],
        [SectorIndexRecord(symbol="NIFTY BANK", display_name="Nifty Bank", is_active=True)],
    ]

    response = client.get("/api/v1/settings/watchlist")

    assert response.status_code == 200
    body = response.json()
    assert body["constituents"][0]["symbol"] == "RELIANCE"
    assert body["sectors"][0]["symbol"] == "NIFTY BANK"


def test_toggle_constituent(client, fake_db_session):
    row = WatchlistConstituent(symbol="RELIANCE", display_name="Reliance", is_active=True)
    fake_db_session.execute.return_value.scalar_one_or_none.return_value = row

    response = client.patch("/api/v1/settings/watchlist/constituents/RELIANCE", json={"is_active": False})

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert fake_db_session.commit.called


def test_toggle_constituent_not_found(client, fake_db_session):
    fake_db_session.execute.return_value.scalar_one_or_none.return_value = None

    response = client.patch("/api/v1/settings/watchlist/constituents/BOGUS", json={"is_active": False})

    assert response.status_code == 400


def test_toggle_sector(client, fake_db_session):
    row = SectorIndexRecord(symbol="NIFTY IT", display_name="Nifty IT", is_active=True)
    fake_db_session.execute.return_value.scalar_one_or_none.return_value = row

    response = client.patch("/api/v1/settings/watchlist/sectors/NIFTY IT", json={"is_active": False})

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_get_risk_settings(client, fake_db_session):
    fake_db_session.execute.return_value.scalar_one_or_none.side_effect = [_founder(), _risk_row()]

    response = client.get("/api/v1/settings/risk")

    assert response.status_code == 200
    body = response.json()
    assert body["vix_normal_max"] == 15.0
    assert body["execution_mode"] == "paper"


def test_get_risk_settings_not_found(client, fake_db_session):
    fake_db_session.execute.return_value.scalar_one_or_none.side_effect = [_founder(), None]

    response = client.get("/api/v1/settings/risk")

    assert response.status_code == 400


def test_update_risk_settings_partial(client, fake_db_session):
    row = _risk_row()
    fake_db_session.execute.return_value.scalar_one_or_none.side_effect = [_founder(), row]

    response = client.put("/api/v1/settings/risk", json={"vix_normal_max": 12.0})

    assert response.status_code == 200
    assert response.json()["vix_normal_max"] == 12.0
    assert response.json()["vix_elevated_max"] == 20.0  # untouched
    assert fake_db_session.commit.called


def test_update_risk_settings_rejects_invalid_execution_mode(client):
    response = client.put("/api/v1/settings/risk", json={"execution_mode": "live_algo"})

    assert response.status_code == 400
    assert "execution_mode" in response.json()["detail"]


def test_update_risk_settings_accepts_live_manual(client, fake_db_session):
    row = _risk_row()
    fake_db_session.execute.return_value.scalar_one_or_none.side_effect = [_founder(), row]

    response = client.put("/api/v1/settings/risk", json={"execution_mode": "live_manual"})

    assert response.status_code == 200
    assert response.json()["execution_mode"] == "live_manual"


def test_alerts_status_reports_unconfigured_by_default(client):
    response = client.get("/api/v1/settings/alerts")

    assert response.status_code == 200
    body = response.json()
    assert body["telegram_configured"] is False
    assert body["email_configured"] is False
    assert body["dashboard_configured"] is True


def test_alerts_status_reports_configured_when_env_set(fake_db_session):
    def _override_get_db():
        yield fake_db_session

    shared_cache = RedisCache(fakeredis.FakeRedis(decode_responses=True))
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis_cache] = lambda: shared_cache
    app.dependency_overrides[get_settings] = lambda: _fake_settings(
        TELEGRAM_BOT_TOKEN="tok", TELEGRAM_CHAT_ID="123",
        SMTP_HOST="smtp.example.com", SMTP_USER="u", SMTP_PASSWORD="p", ALERT_EMAIL_TO="me@example.com",
    )
    app.dependency_overrides[get_market_data_client] = lambda: MagicMock()
    client = TestClient(app)

    response = client.get("/api/v1/settings/alerts")

    app.dependency_overrides.clear()
    assert response.json()["telegram_configured"] is True
    assert response.json()["email_configured"] is True
