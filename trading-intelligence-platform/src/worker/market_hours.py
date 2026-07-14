"""NSE market-hours gate for the worker service (Phase 8, worker service
pass). Pure function, no I/O — takes the current instant, returns whether
the worker should scan right now.

No NSE holiday calendar in MVP: a holiday still passes this check (weekday,
within 09:15-15:30 IST) and the worker will scan on it — sample-mode data
doesn't care, and live-mode Kite calls against a closed market just return
stale/empty candles, which src/market_data's own MIN_CANDLES_FOR_RECOMMENDATION
guard already rejects rather than firing a bad recommendation
(docs/CLAUDE.md section 6). Flagged as a known gap, not silently assumed
away — see docs/assumptions.md.
"""

from datetime import datetime, time

from src.engine.seasonality import IST

MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)


def is_market_open(now_utc: datetime) -> bool:
    """now_utc: any timezone-aware datetime, converted to IST for the check."""
    now_ist = now_utc.astimezone(IST)
    if now_ist.weekday() >= 5:  # Monday=0 ... Sunday=6; Saturday/Sunday excluded.
        return False
    return MARKET_OPEN <= now_ist.time() <= MARKET_CLOSE
