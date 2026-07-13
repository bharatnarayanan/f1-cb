"""Tests for src/routes/recommendations.py — route wiring only.

Same dependency_overrides pattern as tests/test_scan.py: DB/Redis/market
client are all fakes. ANTHROPIC_API_KEY is left unset in _fake_settings so
narration deterministically returns its "not configured" placeholder — see
tests/test_narration.py for narration's own behavior under a real key.
"""

import uuid
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
    candles = [_candle(i, 100.0, 100.3, 99.9, 100.2) for i in range(count - 2)]
    candles.append(_candle(count - 2, 100.0, 101.0, 98.0, 99.0))
    candles.append(_candle(count - 1, 98.5, 103.0, 98.0, 102.0))
    return candles


def _flat_candles(count: int = 40) -> list[dict]:
    return [_candle(i, 100.0, 100.3, 99.9, 100.2) for i in range(count)]


@pytest.fixture
def fake_db_session():
    session = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = ["RELIANCE"]
    return session


@pytest.fixture
def fake_market_client():
    client = MagicMock()
    client.get_instruments.return_value = [
        {"instrument_token": 256265, "tradingsymbol": "NIFTY 50", "exchange": "NSE"},
        {"instrument_token": 738561, "tradingsymbol": "RELIANCE", "exchange": "NSE"},
    ]
    client.get_historical_candles.return_value = _candles_with_a_trailing_engulfing()
    client.get_quote.return_value = {"NSE:INDIA VIX": {"last_price": 12.5}}
    return client


@pytest.fixture
def client(fake_db_session, fake_market_client, monkeypatch):
    def _override_get_db():
        yield fake_db_session

    shared_cache = RedisCache(fakeredis.FakeRedis(decode_responses=True))

    # Route-level tests care about recommendation behavior given a VIX
    # regime, not threshold resolution (src/db/risk_settings.py's own tests
    # cover that) — a fully-mocked db session's execute() chain otherwise
    # silently resolves float(MagicMock()) == 1.0 for every threshold,
    # misclassifying any realistic VIX value as "extreme".
    monkeypatch.setattr("src.routes.recommendations.get_vix_thresholds", lambda db, settings: (15.0, 20.0, 30.0))

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis_cache] = lambda: shared_cache
    app.dependency_overrides[get_settings] = _fake_settings
    app.dependency_overrides[get_market_data_client] = lambda: fake_market_client
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_creates_a_tactical_recommendation_with_full_rationale(client, fake_db_session):
    response = client.post("/api/v1/recommendations/NIFTY 50")

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "NSE:NIFTY 50"
    assert body["data_mode"] == "sample"
    rec = body["recommendation"]
    assert rec is not None
    assert rec["category"] in ("tactical", "impulse")
    assert rec["action"] in ("BUY_CE", "BUY_PE")
    assert 0 <= rec["confidence_score"] <= 100
    assert 0 <= rec["risk_score"] <= 100
    assert "narrative" in rec["rationale"]
    assert "not configured" in rec["rationale"]["narrative"].lower()
    assert fake_db_session.commit.called


def test_returns_no_recommendation_when_nothing_detected(client, fake_market_client):
    fake_market_client.get_historical_candles.return_value = _flat_candles()

    response = client.post("/api/v1/recommendations/NIFTY 50")

    assert response.status_code == 200
    body = response.json()
    assert body["recommendation"] is None
    assert "message" in body


def test_rejects_unsupported_timeframe(client):
    response = client.post("/api/v1/recommendations/NIFTY 50?timeframe=1d")

    assert response.status_code == 400
    assert response.json()["code"] == "data_source_invalid_request"


def test_surfaces_400_for_unresolvable_symbol(client, fake_market_client):
    fake_market_client.get_instruments.return_value = []

    response = client.post("/api/v1/recommendations/BOGUS")

    assert response.status_code == 400


def test_surfaces_400_when_not_enough_candles(client, fake_market_client):
    fake_market_client.get_historical_candles.return_value = [_candle(0, 100, 101, 99, 100)]

    response = client.post("/api/v1/recommendations/NIFTY 50")

    assert response.status_code == 400


def test_create_response_includes_the_recommendation_id(client):
    response = client.post("/api/v1/recommendations/NIFTY 50")

    assert response.status_code == 200
    assert "id" in response.json()["recommendation"]


def test_list_recommendations(client, fake_db_session):
    from src.db.models import Recommendation

    row = Recommendation(
        id=uuid.uuid4(), category="tactical", symbol="NSE:NIFTY 50", action="BUY_CE",
        confidence_score=70.0, risk_score=20.0, conviction_score=63.0,
        rationale={}, vix_regime_at_creation="normal", status="active",
        created_at=datetime.now(),
    )
    fake_db_session.execute.return_value.scalars.return_value.all.return_value = [row]

    response = client.get("/api/v1/recommendations")

    assert response.status_code == 200
    body = response.json()["recommendations"]
    assert len(body) == 1
    assert body[0]["symbol"] == "NSE:NIFTY 50"


def test_get_recommendation_detail(client, fake_db_session):
    from src.db.models import Recommendation

    rec_id = uuid.uuid4()
    row = Recommendation(
        id=rec_id, category="tactical", symbol="NSE:NIFTY 50", action="BUY_CE",
        confidence_score=70.0, risk_score=20.0, conviction_score=63.0,
        rationale={"pattern": {"type": "engulfing"}}, vix_regime_at_creation="normal", status="active",
        created_at=datetime.now(),
    )
    fake_db_session.get.return_value = row

    response = client.get(f"/api/v1/recommendations/{rec_id}")

    assert response.status_code == 200
    assert response.json()["rationale"]["pattern"]["type"] == "engulfing"


def test_get_recommendation_not_found(client, fake_db_session):
    fake_db_session.get.return_value = None

    response = client.get(f"/api/v1/recommendations/{uuid.uuid4()}")

    assert response.status_code == 400


def test_get_recommendation_invalid_id(client):
    response = client.get("/api/v1/recommendations/not-a-uuid")

    assert response.status_code == 400


def test_alert_logs_reference_the_flushed_recommendation_id(client, fake_db_session):
    """Regression test for a live-caught bug: Recommendation.id (default=
    uuid.uuid4) is populated by SQLAlchemy at flush time, NOT at object
    construction (confirmed: `Recommendation(...).id` is None right after
    construction) — dispatch_alerts must run AFTER db.flush(), or every
    AlertLog.recommendation_id stays None and violates alerts_log's NOT
    NULL constraint at commit. A fully-mocked db.flush() is a no-op, so
    this test simulates real flush behavior explicitly (assigning an id on
    flush) — a plain MagicMock alone would not have caught this.
    """
    added_objects = []

    def _add(obj):
        added_objects.append(obj)

    def _flush():
        for obj in added_objects:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    fake_db_session.add.side_effect = _add
    fake_db_session.flush.side_effect = _flush

    response = client.post("/api/v1/recommendations/NIFTY 50")

    assert response.status_code == 200
    from src.db.models import AlertLog, Recommendation

    recommendation = next(obj for obj in added_objects if isinstance(obj, Recommendation))
    alert_logs = [obj for obj in added_objects if isinstance(obj, AlertLog)]
    assert alert_logs, "expected AlertLog rows to have been added"
    assert recommendation.id is not None
    assert all(log.recommendation_id == recommendation.id for log in alert_logs)
