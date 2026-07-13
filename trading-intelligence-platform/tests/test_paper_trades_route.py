"""Tests for src/routes/paper_trades.py — route wiring only."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import fakeredis
import pytest
from fastapi.testclient import TestClient

from src.cache.redis_client import RedisCache, get_redis_cache
from src.config import Settings, get_settings
from src.db.models import PaperTrade, Recommendation, User
from src.db.session import get_db
from src.main import app
from src.market_data.factory import get_market_data_client

_FOUNDER_ID = uuid.uuid4()
_RECOMMENDATION_ID = uuid.uuid4()
_TRADE_ID = uuid.uuid4()

_START = datetime(2026, 7, 1, 9, 15)


def _fake_settings() -> Settings:
    return Settings(
        SECRET_KEY="test-secret", DATABASE_URL="sqlite:///:memory:",
        KITE_API_KEY="test-key", KITE_ACCESS_TOKEN="test-token", DATA_MODE="sample",
    )


def _founder() -> User:
    return User(id=_FOUNDER_ID, email="founder@local", hashed_password="x", display_name="Founder")


def _recommendation(action: str = "BUY_CE") -> Recommendation:
    future_expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    return Recommendation(
        id=_RECOMMENDATION_ID, category="tactical", symbol="NSE:NIFTY 50", action=action,
        confidence_score=70.0, risk_score=20.0, conviction_score=63.0,
        rationale={"negation": {"predicted_window_end": future_expiry}},
        vix_regime_at_creation="normal",
    )


def _open_trade() -> PaperTrade:
    # Postgres Numeric columns come back as decimal.Decimal, not float — a
    # live-caught bug had compute_pnl_pct's subtraction crash on Decimal-
    # minus-float (TypeError). Using Decimal here (not plain floats) makes
    # every close test in this file a real regression guard for that.
    return PaperTrade(
        id=_TRADE_ID, recommendation_id=_RECOMMENDATION_ID, user_id=_FOUNDER_ID,
        simulated_entry_price=Decimal("100.0"), status="open",
        target_price=Decimal("110.0"), stop_loss_price=Decimal("95.0"),
        expiry_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )


def _candle(i: int, o: float, h: float, l: float, c: float) -> dict:
    return {"date": _START + timedelta(minutes=5 * i), "open": o, "high": h, "low": l, "close": c, "volume": 1000}


@pytest.fixture
def fake_db_session():
    session = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = _founder()
    session.execute.return_value.scalars.return_value.all.return_value = []

    def _get(model, obj_id):
        if model is Recommendation:
            return _recommendation()
        if model is PaperTrade:
            return _open_trade()
        return None

    session.get.side_effect = _get
    return session


@pytest.fixture
def fake_market_client():
    client = MagicMock()
    client.get_instruments.return_value = [{"instrument_token": 256265, "tradingsymbol": "NIFTY 50", "exchange": "NSE"}]
    client.get_historical_candles.return_value = [_candle(i, 100, 100.3, 99.9, 100.2) for i in range(40)]
    client.get_quote.return_value = {"NSE:NIFTY 50": {"last_price": 105.0}}
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
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_open_paper_trade(client, fake_db_session):
    response = client.post("/api/v1/paper-trades", json={"recommendation_id": str(_RECOMMENDATION_ID)})

    assert response.status_code == 200
    body = response.json()
    assert body["simulated_entry_price"] == 105.0
    assert body["status"] == "open"
    assert fake_db_session.commit.called


def test_open_paper_trade_rejects_no_trade_action(client, fake_db_session):
    fake_db_session.get.side_effect = lambda model, oid: _recommendation(action="NO_TRADE") if model is Recommendation else None

    response = client.post("/api/v1/paper-trades", json={"recommendation_id": str(_RECOMMENDATION_ID)})

    assert response.status_code == 400


def test_close_paper_trade_still_open_when_nothing_triggered(client, fake_market_client):
    fake_market_client.get_quote.return_value = {"NSE:NIFTY 50": {"last_price": 100.5}}  # between target/stop

    response = client.post(f"/api/v1/paper-trades/{_TRADE_ID}/close")

    assert response.status_code == 200
    assert response.json()["status"] == "open"


def test_close_paper_trade_hits_target(client, fake_market_client):
    fake_market_client.get_quote.return_value = {"NSE:NIFTY 50": {"last_price": 112.0}}

    response = client.post(f"/api/v1/paper-trades/{_TRADE_ID}/close")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "closed"
    assert body["close_reason"] == "target"
    assert body["simulated_pnl_pct"] == 12.0


def test_close_paper_trade_forced(client, fake_market_client):
    fake_market_client.get_quote.return_value = {"NSE:NIFTY 50": {"last_price": 101.0}}

    response = client.post(f"/api/v1/paper-trades/{_TRADE_ID}/close", json={"force": True})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "closed"
    assert body["close_reason"] == "forced"


def test_close_already_closed_trade_is_idempotent(client, fake_db_session):
    closed_trade = _open_trade()
    closed_trade.status = "closed"
    closed_trade.simulated_pnl_pct = 5.0
    fake_db_session.get.side_effect = lambda model, oid: closed_trade if model is PaperTrade else _recommendation()

    response = client.post(f"/api/v1/paper-trades/{_TRADE_ID}/close")

    assert response.status_code == 200
    assert response.json()["already_closed"] is True


def test_list_paper_trades(client, fake_db_session):
    fake_db_session.execute.return_value.scalars.return_value.all.return_value = [_open_trade()]

    response = client.get("/api/v1/paper-trades")

    assert response.status_code == 200
    trades = response.json()["paper_trades"]
    assert len(trades) == 1
    assert "opened_at" in trades[0]  # needed by the frontend equity curve chart


def test_open_paper_trade_invalid_recommendation_id(client):
    response = client.post("/api/v1/paper-trades", json={"recommendation_id": "not-a-uuid"})

    assert response.status_code == 400
