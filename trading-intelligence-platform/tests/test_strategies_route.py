"""Tests for src/routes/strategies.py — route wiring only.

Same dependency_overrides pattern as tests/test_scan.py. Real Strategy/User
ORM instances are used as fake DB return values (they're plain Python
objects until attached to a real session) so tests configure the mock
session's query methods, not every model attribute by hand.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import fakeredis
import pytest
from fastapi.testclient import TestClient

from src.auth.dependencies import get_current_user
from src.cache.redis_client import RedisCache, get_redis_cache
from src.config import Settings, get_settings
from src.db.models import Strategy, User
from src.db.session import get_db
from src.main import app
from src.market_data.factory import get_market_data_client

_FOUNDER_ID = uuid.uuid4()
_BVWR_ID = uuid.uuid4()

_BVWR_CANONICAL_LOGIC = {
    "version": "1.0",
    "instrument": {"underlying": "NIFTY", "leg": "either"},
    "timeframe": "15m",
    "entry": {"logic": "AND", "conditions": [{"left": {"field": "close"}, "operator": ">", "right": {"indicator": "SMA", "period": 50}}]},
    "exit": {
        "targets": [{"type": "prior_candle_high"}],
        "stop_loss": {"type": "below_ma", "reference_indicator": {"indicator": "SMA", "period": 50}},
    },
    "guards": [],
    "is_preset": True,
}

_START = datetime(2026, 7, 1, 9, 15)


def _fake_settings() -> Settings:
    return Settings(
        SECRET_KEY="test-secret",
        DATABASE_URL="sqlite:///:memory:",
        KITE_API_KEY="test-key",
        KITE_ACCESS_TOKEN="test-token",
        DATA_MODE="sample",
    )


def _founder() -> User:
    return User(id=_FOUNDER_ID, email="founder@local", hashed_password="x", display_name="Founder")


def _bvwr_strategy() -> Strategy:
    return Strategy(
        id=_BVWR_ID, name="BVWR", source_type="user_rule", raw_input=None,
        canonical_logic=_BVWR_CANONICAL_LOGIC, status="extracted", created_by=_FOUNDER_ID,
    )


def _candle(i: int, o: float, h: float, l: float, c: float) -> dict:
    return {"date": _START + timedelta(minutes=5 * i), "open": o, "high": h, "low": l, "close": c, "volume": 1000}


def _many_candles(count: int = 200) -> list[dict]:
    return [_candle(i, 100 + i * 0.01, 100.5 + i * 0.01, 99.5 + i * 0.01, 100.2 + i * 0.01) for i in range(count)]


@pytest.fixture
def fake_db_session():
    session = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = _founder()
    session.execute.return_value.scalars.return_value.all.return_value = [_bvwr_strategy()]
    session.get.return_value = _bvwr_strategy()
    return session


@pytest.fixture
def fake_market_client():
    client = MagicMock()
    client.get_instruments.return_value = [{"instrument_token": 256265, "tradingsymbol": "NIFTY 50", "exchange": "NSE"}]
    client.get_historical_candles.return_value = _many_candles()
    return client


@pytest.fixture
def client(fake_db_session, fake_market_client):
    def _override_get_db():
        yield fake_db_session

    shared_cache = RedisCache(fakeredis.FakeRedis(decode_responses=True))

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis_cache] = lambda: shared_cache
    app.dependency_overrides[get_settings] = _fake_settings
    app.dependency_overrides[get_market_data_client] = lambda: fake_market_client
    app.dependency_overrides[get_current_user] = _founder
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_list_strategies(client):
    response = client.get("/api/v1/strategies")

    assert response.status_code == 200
    assert response.json()["strategies"][0]["name"] == "BVWR"


def test_get_strategy(client):
    response = client.get(f"/api/v1/strategies/{_BVWR_ID}")

    assert response.status_code == 200
    assert response.json()["canonical_logic"]["instrument"]["underlying"] == "NIFTY"


def test_get_strategy_not_found(client, fake_db_session):
    fake_db_session.get.return_value = None

    response = client.get(f"/api/v1/strategies/{uuid.uuid4()}")

    assert response.status_code == 400


def test_get_strategy_invalid_id(client):
    response = client.get("/api/v1/strategies/not-a-uuid")

    assert response.status_code == 400


def test_ingest_strategy_without_anthropic_key_stays_ingested(client, fake_db_session):
    response = client.post(
        "/api/v1/strategies",
        json={"name": "New Strategy", "source_type": "text", "raw_input": "buy when RSI < 30"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ingested"
    assert body["canonical_logic"] is None
    assert "ANTHROPIC_API_KEY" in body["extraction_error"]
    assert fake_db_session.commit.called


def test_ingest_strategy_rejects_unsupported_source_type(client):
    response = client.post(
        "/api/v1/strategies",
        json={"name": "Bad", "source_type": "audio", "raw_input": "x"},
    )

    assert response.status_code == 400


def test_backtest_strategy(client, fake_db_session):
    response = client.post(f"/api/v1/strategies/{_BVWR_ID}/backtest")

    assert response.status_code == 200
    body = response.json()
    assert body["data_mode"] == "sample"
    assert "confidence_score" in body
    assert "assumptions" in body
    assert fake_db_session.commit.called


def test_backtest_strategy_without_canonical_logic(client, fake_db_session):
    strategy = _bvwr_strategy()
    strategy.canonical_logic = None
    fake_db_session.get.return_value = strategy

    response = client.post(f"/api/v1/strategies/{_BVWR_ID}/backtest")

    assert response.status_code == 400


def test_fuse_strategies(client):
    response = client.post(
        "/api/v1/strategies/fuse",
        json={"name": "Fused", "base_strategy_id": str(_BVWR_ID), "other_strategy_id": str(_BVWR_ID)},
    )

    assert response.status_code == 200
    body = response.json()
    assert "fused_strategy_id" in body
    assert body["resolved_logic"]["is_preset"] is False


def test_export_strategy(client):
    response = client.get(f"/api/v1/strategies/{_BVWR_ID}/export")

    assert response.status_code == 200
    assert "//@version=5" in response.json()["pine_script"]


def test_export_strategy_without_canonical_logic(client, fake_db_session):
    strategy = _bvwr_strategy()
    strategy.canonical_logic = None
    fake_db_session.get.return_value = strategy

    response = client.get(f"/api/v1/strategies/{_BVWR_ID}/export")

    assert response.status_code == 400
