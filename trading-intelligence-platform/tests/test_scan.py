"""Tests for src/routes/scan.py — the on-demand F3.1-F3.4 scan route.

Same dependency_overrides pattern as tests/test_api.py: DB/Redis/market
client are all fakes, so these test route wiring (input validation,
response shape, DB writes) without needing live infra or real TA-Lib
pattern math (that's tests/test_patterns.py etc's job).
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import fakeredis
import pytest
from fastapi.testclient import TestClient

from src.cache.redis_client import RedisCache, get_redis_cache
from src.config import Settings, get_settings
from src.db.session import get_db
from src.main import app
from src.market_data.factory import get_market_data_client

_START = datetime(2026, 7, 1, 9, 15)


def _fake_settings() -> Settings:
    return Settings(
        SECRET_KEY="test-secret",
        DATABASE_URL="sqlite:///:memory:",
        KITE_API_KEY="test-key",
        KITE_ACCESS_TOKEN="test-token",
        DATA_MODE="sample",
    )


def _candle(i: int, o: float, h: float, l: float, c: float) -> dict:
    return {"date": _START + timedelta(minutes=5 * i), "open": o, "high": h, "low": l, "close": c, "volume": 1000}


def _candles_with_a_trailing_engulfing(count: int = 40) -> list[dict]:
    # Filler body (0.2) dominates its range (0.4) - immune to doji/pin-bar
    # false positives, same reasoning as tests/test_patterns.py's _FILLER.
    candles = [_candle(i, 100.0, 100.3, 99.9, 100.2) for i in range(count - 2)]
    last = count - 1
    candles.append(_candle(last - 1, 100.0, 101.0, 98.0, 99.0))   # small bearish body
    candles.append(_candle(last, 98.5, 103.0, 98.0, 102.0))       # engulfs it
    return candles


@pytest.fixture
def fake_db_session():
    session = MagicMock()
    return session


@pytest.fixture
def fake_market_client():
    client = MagicMock()
    client.get_instruments.return_value = [
        {"instrument_token": 256265, "tradingsymbol": "NIFTY 50", "exchange": "NSE"},
    ]
    client.get_historical_candles.return_value = _candles_with_a_trailing_engulfing()
    client.get_quote.return_value = {"NSE:INDIA VIX": {"last_price": 12.5}}
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


def test_scan_returns_patterns_negations_and_sr_levels(client, fake_db_session):
    response = client.post("/api/v1/scan/NIFTY 50")

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "NSE:NIFTY 50"
    assert body["data_mode"] == "sample"
    assert body["vix_regime"] == "normal"
    assert body["candles_scanned"] == 40
    assert any(p["timeframe"] == "5m" for p in body["patterns_detected"])
    assert any(n["timeframe"] == "5m" for n in body["negation_predictions"])
    assert fake_db_session.commit.called


def test_scan_surfaces_400_for_unresolvable_symbol(client, fake_market_client):
    fake_market_client.get_instruments.return_value = []

    response = client.post("/api/v1/scan/BOGUS")

    assert response.status_code == 400
    assert response.json()["code"] == "data_source_invalid_request"


def test_scan_surfaces_400_when_not_enough_candles(client, fake_market_client):
    fake_market_client.get_historical_candles.return_value = [_candle(0, 100, 101, 99, 100)]

    response = client.post("/api/v1/scan/NIFTY 50")

    assert response.status_code == 400
    assert response.json()["code"] == "data_source_invalid_request"
