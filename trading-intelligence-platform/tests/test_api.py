"""FastAPI route tests (src/main.py, src/routes/market.py).

All external dependencies (DB, Redis, Kite) are overridden with fakes via
FastAPI's dependency_overrides — no real Postgres/Redis/Zerodha needed for
these to pass. That's deliberate: route wiring should be testable without
live infra, while tests/test_market_data.py, tests/test_cache.py, and the
manual docker-compose smoke check cover the real integrations.
"""

from unittest.mock import MagicMock

import fakeredis
import pytest
from fastapi.testclient import TestClient

from sqlalchemy.exc import SQLAlchemyError

from src.cache.redis_client import RedisCache, get_redis_cache
from src.config import Settings, get_settings
from src.db.session import get_db
from src.main import app
from src.market_data.exceptions import (
    MarketDataAuthError,
    MarketDataInvalidRequest,
    MarketDataUnavailable,
)
from src.market_data.factory import get_market_data_client


def _fake_settings() -> Settings:
    # Settings fields are populated by their env-var alias (SECRET_KEY, ...),
    # not the Python attribute name — see src/config.py.
    return Settings(
        SECRET_KEY="test-secret",
        DATABASE_URL="sqlite:///:memory:",
        KITE_API_KEY="test-key",
        KITE_ACCESS_TOKEN="test-token",
        # Pinned explicitly (not left to the env-var/`.env` default) so
        # these tests can't flip result depending on a developer's local
        # DATA_MODE setting.
        DATA_MODE="sample",
    )


@pytest.fixture
def fake_db_session():
    session = MagicMock()
    session.execute.return_value = None
    return session


@pytest.fixture
def fake_market_client():
    return MagicMock()


@pytest.fixture
def client(fake_db_session, fake_market_client):
    def _override_get_db():
        yield fake_db_session

    # One shared fake-Redis instance for the life of the test — a fresh
    # instance per call (as a naive `lambda: RedisCache(fakeredis.FakeRedis())`
    # would give) would defeat caching, since nothing would ever be found on
    # a later request.
    shared_cache = RedisCache(fakeredis.FakeRedis(decode_responses=True))

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis_cache] = lambda: shared_cache
    app.dependency_overrides[get_settings] = _fake_settings
    app.dependency_overrides[get_market_data_client] = lambda: fake_market_client
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health_reports_ok_when_dependencies_are_up(client):
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["redis"] == "ok"
    assert body["kite"] == "configured"
    assert body["data_mode"] == "sample"
    assert "no order" in body["safety_notice"].lower() or "no real order" in body["safety_notice"].lower()


def test_health_reports_degraded_when_db_down(client, fake_db_session):
    fake_db_session.execute.side_effect = RuntimeError("connection refused")

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "unreachable"


def test_get_quote_returns_live_price_and_caches_it(client, fake_market_client):
    fake_market_client.get_quote.return_value = {"NSE:NIFTY 50": {"last_price": 24500.1}}

    first = client.get("/api/v1/market/quote/NIFTY 50")
    second = client.get("/api/v1/market/quote/NIFTY 50")

    assert first.status_code == 200
    assert first.json()["last_price"] == 24500.1
    assert first.json()["cached"] is False
    assert first.json()["data_mode"] == "sample"
    assert second.json()["cached"] is True
    # Only one real upstream call — the second request was served from cache.
    fake_market_client.get_quote.assert_called_once()


def test_get_quote_surfaces_503_when_data_source_unavailable(client, fake_market_client):
    fake_market_client.get_quote.side_effect = MarketDataUnavailable("Kite unreachable")

    response = client.get("/api/v1/market/quote/NIFTY 50")

    assert response.status_code == 503
    assert response.json()["code"] == "data_source_unavailable"


def test_get_quote_surfaces_401_when_token_invalid(client, fake_market_client):
    fake_market_client.get_quote.side_effect = MarketDataAuthError("token expired")

    response = client.get("/api/v1/market/quote/NIFTY 50")

    assert response.status_code == 401
    assert response.json()["code"] == "data_source_auth_error"


def test_get_quote_surfaces_400_when_symbol_missing_from_response(client, fake_market_client):
    # Kite's ltp() can succeed without raising yet omit the requested key
    # (e.g. a malformed symbol it silently ignores) — the route must not
    # let that raise an unhandled KeyError.
    fake_market_client.get_quote.return_value = {}

    response = client.get("/api/v1/market/quote/NIFTY 50")

    assert response.status_code == 400
    assert response.json()["code"] == "data_source_invalid_request"


def test_get_quote_surfaces_400_when_kite_rejects_the_request(client, fake_market_client):
    fake_market_client.get_quote.side_effect = MarketDataInvalidRequest("unknown symbol")

    response = client.get("/api/v1/market/quote/NIFTY 50")

    assert response.status_code == 400
    assert response.json()["code"] == "data_source_invalid_request"


def test_get_vix_is_cached_and_skips_duplicate_db_write(client, fake_market_client, fake_db_session):
    fake_market_client.get_quote.return_value = {"NSE:INDIA VIX": {"last_price": 12.5}}

    first = client.get("/api/v1/market/vix")
    second = client.get("/api/v1/market/vix")

    assert first.json()["cached"] is False
    assert second.json()["cached"] is True
    fake_market_client.get_quote.assert_called_once()
    fake_db_session.add.assert_called_once()
    fake_db_session.commit.assert_called_once()


def test_get_vix_surfaces_503_when_db_write_fails(client, fake_market_client, fake_db_session):
    fake_market_client.get_quote.return_value = {"NSE:INDIA VIX": {"last_price": 12.5}}
    fake_db_session.commit.side_effect = SQLAlchemyError("connection reset")

    response = client.get("/api/v1/market/vix")

    assert response.status_code == 503
    assert response.json()["code"] == "storage_unavailable"
    fake_db_session.rollback.assert_called_once()


def test_get_vix_computes_regime_and_persists_snapshot(client, fake_market_client, fake_db_session):
    fake_market_client.get_quote.return_value = {"NSE:INDIA VIX": {"last_price": 12.5}}

    response = client.get("/api/v1/market/vix")

    assert response.status_code == 200
    body = response.json()
    assert body["value"] == 12.5
    assert body["regime"] == "normal"
    fake_db_session.add.assert_called_once()
    fake_db_session.commit.assert_called_once()


def test_get_vix_flags_extreme_regime(client, fake_market_client):
    fake_market_client.get_quote.return_value = {"NSE:INDIA VIX": {"last_price": 35.0}}

    response = client.get("/api/v1/market/vix")

    assert response.json()["regime"] == "extreme"


def test_no_route_places_or_modifies_or_cancels_an_order(client):
    routes = {route.path for route in app.routes}
    forbidden_fragments = ("place_order", "modify_order", "cancel_order", "/order")
    assert not any(frag in path for path in routes for frag in forbidden_fragments)
