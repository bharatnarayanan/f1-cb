"""Read-only market-data routes (docs/api_routes.md -> "Market data").

Every route here either reads from TimescaleDB or makes an on-demand,
read-only Kite Connect call cached in Redis. No route in this file (or
anywhere else in this codebase) places, modifies, or cancels a broker
order — see docs/CLAUDE.md section 2.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.cache.redis_client import DEFAULT_QUOTE_TTL_SECONDS, RedisCache, get_redis_cache
from src.config import Settings, get_settings
from src.db.models import IndiaVixSnapshot
from src.db.risk_settings import get_vix_thresholds
from src.db.session import get_db
from src.market_data.base import MarketDataClient
from src.market_data.exceptions import MarketDataInvalidRequest
from src.market_data.factory import get_market_data_client
from src.market_data.vix import compute_vix_regime

VIX_CACHE_KEY_PREFIX = "vix"

router = APIRouter(prefix="/api/v1/market", tags=["market"])


@router.get("/quote/{symbol}")
def get_quote(
    symbol: str,
    exchange: str = "NSE",
    market: MarketDataClient = Depends(get_market_data_client),
    cache: RedisCache = Depends(get_redis_cache),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Latest live price for one symbol, e.g. GET /quote/NIFTY 50.

    Cached in Redis for DEFAULT_QUOTE_TTL_SECONDS so repeated dashboard
    refreshes don't burn Zerodha's rate limit on every request.
    """
    kite_symbol = f"{exchange}:{symbol}"
    cache_key = f"quote:{kite_symbol}:{settings.data_mode}"

    cached = cache.get_json(cache_key)
    if cached is not None:
        return {**cached, "cached": True}

    quote = market.get_quote([kite_symbol])
    if kite_symbol not in quote:
        raise MarketDataInvalidRequest(
            f"Kite Connect returned no data for {kite_symbol} — check the symbol/exchange."
        )
    data = quote[kite_symbol]
    result = {
        "symbol": kite_symbol,
        "last_price": data["last_price"],
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "data_mode": settings.data_mode,
    }
    cache.set_json(cache_key, result, ttl_seconds=DEFAULT_QUOTE_TTL_SECONDS)
    return {**result, "cached": False}


@router.get("/vix")
def get_vix(
    market: MarketDataClient = Depends(get_market_data_client),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
    cache: RedisCache = Depends(get_redis_cache),
) -> dict:
    """Latest India VIX value + regime. Fetches live, then persists a
    snapshot row (india_vix_snapshots) so the reading isn't lost between
    requests — the worker pipeline (later phase) will take over writing
    these on a schedule; this on-demand path is a Phase 2 stand-in.

    Cached in Redis for DEFAULT_QUOTE_TTL_SECONDS, same as get_quote — a
    cache hit skips both the upstream call and the DB write, so repeated
    polling doesn't burn Zerodha's rate limit or grow india_vix_snapshots
    with duplicate rows for an unchanged reading.
    """
    cache_key = f"{VIX_CACHE_KEY_PREFIX}:{settings.data_mode}"
    cached = cache.get_json(cache_key)
    if cached is not None:
        return {**cached, "cached": True}

    quote = market.get_quote(["NSE:INDIA VIX"])
    if "NSE:INDIA VIX" not in quote:
        raise MarketDataInvalidRequest("Kite Connect returned no data for NSE:INDIA VIX.")
    value = float(quote["NSE:INDIA VIX"]["last_price"])
    normal_max, elevated_max, high_max = get_vix_thresholds(db, settings)
    regime = compute_vix_regime(value, normal_max, elevated_max, high_max)
    now = datetime.now(timezone.utc)

    try:
        db.add(IndiaVixSnapshot(ts=now, value=value, regime=regime))
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    result = {"value": value, "regime": regime, "ts": now.isoformat(), "data_mode": settings.data_mode}
    cache.set_json(cache_key, result, ttl_seconds=DEFAULT_QUOTE_TTL_SECONDS)
    return {**result, "cached": False}
