"""Tests for src/recommendation_pipeline.py's dedup_cache integration
(Phase 8, worker service pass) — the on-demand route never passes
dedup_cache (tests/test_recommendations_route.py covers that path
unchanged); these tests cover the worker's opt-in behavior directly.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import fakeredis
import pytest

from src.cache.redis_client import RedisCache
from src.config import Settings
from src.db.risk_settings import GuardrailSettings
from src.recommendation_pipeline import generate_recommendation

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
    candles = [_candle(i, 100.0, 100.3, 99.9, 100.2) for i in range(count - 2)]
    candles.append(_candle(count - 2, 100.0, 101.0, 98.0, 99.0))
    candles.append(_candle(count - 1, 98.5, 103.0, 98.0, 102.0))
    return candles


@pytest.fixture
def fake_db_session():
    session = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = ["RELIANCE"]
    session.execute.return_value.scalar_one.return_value = 0
    return session


@pytest.fixture
def fake_market_client():
    client = MagicMock()
    client.get_instruments.return_value = [
        {"instrument_token": 738561, "tradingsymbol": "RELIANCE", "exchange": "NSE"},
    ]
    client.get_historical_candles.return_value = _candles_with_a_trailing_engulfing()
    client.get_quote.return_value = {"NSE:INDIA VIX": {"last_price": 12.5}}
    return client


@pytest.fixture(autouse=True)
def _patch_thresholds_and_guardrails(monkeypatch):
    monkeypatch.setattr("src.recommendation_pipeline.get_vix_thresholds", lambda db, settings: (15.0, 20.0, 30.0))
    monkeypatch.setattr(
        "src.recommendation_pipeline.get_guardrail_settings",
        lambda db: GuardrailSettings(
            suppress_tactical_on_extreme=True,
            expiry_day_dampening=True,
            expiry_weekday=1,
            max_daily_recommendations=20,
        ),
    )


def test_no_dedup_cache_behaves_like_the_route_always_did(fake_db_session, fake_market_client):
    result = generate_recommendation(
        symbol="RELIANCE", exchange="NSE", timeframe="15m",
        market=fake_market_client, db=fake_db_session, settings=_fake_settings(),
    )

    assert result["recommendation"] is not None


def test_first_call_with_dedup_cache_scans_normally(fake_db_session, fake_market_client):
    cache = RedisCache(fakeredis.FakeRedis(decode_responses=True))

    result = generate_recommendation(
        symbol="RELIANCE", exchange="NSE", timeframe="15m",
        market=fake_market_client, db=fake_db_session, settings=_fake_settings(),
        dedup_cache=cache,
    )

    assert result["recommendation"] is not None


def test_second_call_for_the_same_bar_is_skipped_as_a_duplicate(fake_db_session, fake_market_client):
    cache = RedisCache(fakeredis.FakeRedis(decode_responses=True))
    kwargs = dict(
        symbol="RELIANCE", exchange="NSE", timeframe="15m",
        market=fake_market_client, settings=_fake_settings(), dedup_cache=cache,
    )

    first = generate_recommendation(db=fake_db_session, **kwargs)
    second = generate_recommendation(db=fake_db_session, **kwargs)

    assert first["recommendation"] is not None
    assert second["recommendation"] is None
    assert "already scanned" in second["message"]


def test_a_new_candle_close_is_not_treated_as_a_duplicate(fake_db_session, fake_market_client):
    cache = RedisCache(fakeredis.FakeRedis(decode_responses=True))
    kwargs = dict(
        symbol="RELIANCE", exchange="NSE", timeframe="15m",
        market=fake_market_client, settings=_fake_settings(), dedup_cache=cache,
    )

    first = generate_recommendation(db=fake_db_session, **kwargs)
    # Simulate time passing / a newer candle closing.
    fake_market_client.get_historical_candles.return_value = _candles_with_a_trailing_engulfing(count=44)
    second = generate_recommendation(db=fake_db_session, **kwargs)

    assert first["recommendation"] is not None
    assert second["recommendation"] is not None
