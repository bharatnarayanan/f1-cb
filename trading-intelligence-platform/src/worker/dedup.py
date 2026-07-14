"""Redis-based scan dedup for the worker service (Phase 8, worker service
pass). src/routes/scan.py's docstring has flagged this gap since Phase 3:
"the real worker will dedupe by only ever scanning the newest closed
candle." Backed by Redis — already this stack's cache/coordination layer —
rather than a new DB table: a lost dedup key on a Redis restart just means
the worker re-evaluates one bar it's already seen once, which is harmless,
not a correctness bug, so Redis's best-effort persistence is good enough
here.
"""

from datetime import datetime

from src.cache.redis_client import RedisCache

# Comfortably longer than any timeframe this worker scans (max 2h candles)
# — just bounds key growth, not a correctness requirement.
DEDUP_TTL_SECONDS = 7 * 24 * 60 * 60


def _dedup_key(symbol: str, timeframe: str) -> str:
    return f"worker:last_scanned:{symbol}:{timeframe}"


def already_scanned(cache: RedisCache, symbol: str, timeframe: str, bar_ts: datetime) -> bool:
    return cache.get_json(_dedup_key(symbol, timeframe)) == bar_ts.isoformat()


def mark_scanned(cache: RedisCache, symbol: str, timeframe: str, bar_ts: datetime) -> None:
    cache.set_json(_dedup_key(symbol, timeframe), bar_ts.isoformat(), ttl_seconds=DEDUP_TTL_SECONDS)
