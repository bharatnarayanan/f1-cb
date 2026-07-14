"""Scheduled intelligence pipeline (Phase 8, worker service pass).

Replaces manually curl-ing POST /api/v1/recommendations/{symbol} with an
automatic scan across the active watchlist during real NSE market hours.
Long-running process, NOT FastAPI — run via `docker compose up worker`
(same Dockerfile as `api`, different command; see docker-compose.yml).

Every cycle: for each active watchlist constituent/sector index and each
supported timeframe, calls the same src/recommendation_pipeline.py used by
the on-demand HTTP route, passing dedup_cache so a bar already evaluated
this candle doesn't get re-persisted every tick (src/worker/dedup.py).
Gated on src/worker/market_hours.py so nothing runs outside 09:15-15:30 IST
weekdays.

No function here places, modifies, or cancels a broker order — see
docs/CLAUDE.md section 2.
"""

import logging
import time
from datetime import datetime, timezone

from prometheus_client import start_http_server
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from src.cache.redis_client import get_redis_cache
from src.config import get_settings
from src.db.models import SectorIndexRecord, WatchlistConstituent
from src.db.session import get_session_factory
from src.market_data.exceptions import MarketDataAuthError, MarketDataInvalidRequest, MarketDataUnavailable
from src.market_data.factory import get_market_data_client
from src.recommendation_pipeline import generate_recommendation
from src.worker.market_hours import is_market_open

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Same set src/routes/recommendations.py accepts (ALLOWED_TIMEFRAMES in
# src/recommendation_pipeline.py) — scanned in this fixed order every cycle.
SCAN_TIMEFRAMES = ["15m", "30m", "1h", "2h"]
EXCHANGE = "NSE"

# prometheus_client keeps one in-memory registry per process. The worker
# imports the same Counter/Histogram objects api does (src/metrics.py), but
# they live in a separate process here — without its own HTTP exporter,
# every increment the worker makes (recommendations created/suppressed,
# alerts dispatched) would be invisible to Prometheus, which only scrapes
# api:8000/metrics. This port is a second, independent scrape target.
METRICS_PORT = 9100


def _active_watchlist_symbols(session_factory) -> list[str]:
    db = session_factory()
    try:
        constituents = db.execute(
            select(WatchlistConstituent.symbol).where(WatchlistConstituent.is_active.is_(True))
        ).scalars().all()
        sectors = db.execute(
            select(SectorIndexRecord.symbol).where(SectorIndexRecord.is_active.is_(True))
        ).scalars().all()
        return list(constituents) + list(sectors)
    finally:
        db.close()


def run_one_cycle() -> None:
    settings = get_settings()
    session_factory = get_session_factory()
    market = get_market_data_client()
    cache = get_redis_cache()

    symbols = _active_watchlist_symbols(session_factory)
    logger.info("cycle start: %d active symbols", len(symbols))

    for symbol in symbols:
        for timeframe in SCAN_TIMEFRAMES:
            db = session_factory()
            try:
                result = generate_recommendation(
                    symbol=symbol,
                    exchange=EXCHANGE,
                    timeframe=timeframe,
                    market=market,
                    db=db,
                    settings=settings,
                    dedup_cache=cache,
                )
                if result.get("recommendation") is not None:
                    logger.info("recommendation created symbol=%s timeframe=%s", symbol, timeframe)
                else:
                    logger.info(
                        "no recommendation symbol=%s timeframe=%s reason=%s",
                        symbol, timeframe, result.get("message"),
                    )
            except (MarketDataUnavailable, MarketDataAuthError, MarketDataInvalidRequest) as exc:
                # Per docs/CLAUDE.md section 6: skip, never fabricate — log
                # and move on to the next symbol/timeframe rather than
                # letting one bad data source outage kill the whole cycle.
                logger.warning("data error symbol=%s timeframe=%s error=%s", symbol, timeframe, exc)
            except SQLAlchemyError:
                logger.exception("db error symbol=%s timeframe=%s", symbol, timeframe)
            except Exception:
                # Last-resort safety net — one bad symbol must never take
                # down the rest of the watchlist's cycle (same posture as
                # src/main.py's generic 500 handler).
                logger.exception("unexpected error symbol=%s timeframe=%s", symbol, timeframe)
            finally:
                db.close()

    logger.info("cycle complete")


def main() -> None:
    settings = get_settings()
    interval = settings.pattern_scan_interval_seconds
    start_http_server(METRICS_PORT)
    logger.info("worker starting, scan_interval_seconds=%s, metrics_port=%s", interval, METRICS_PORT)

    while True:
        now_utc = datetime.now(timezone.utc)
        if is_market_open(now_utc):
            try:
                run_one_cycle()
            except Exception:
                logger.exception("cycle-level failure — will retry next interval")
        else:
            logger.debug("market closed, skipping cycle")
        time.sleep(interval)


if __name__ == "__main__":
    main()
