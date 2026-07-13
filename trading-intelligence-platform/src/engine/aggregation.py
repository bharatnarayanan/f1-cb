"""On-demand multi-timeframe candle aggregation (F3.3).

Resamples 5m base candles into 10m/15m/30m/1h/2h/3h bars with pandas —
complements (not replaces) the TimescaleDB continuous aggregates in
database/schema.sql, which only refresh on their scheduled interval. This
path gives the pattern/SR engines a fresh, un-lagged view of the latest
partial bucket without waiting on a materialized-view refresh, e.g. right
after an on-demand market-data fetch.
"""

from typing import Any

import pandas as pd

_RESAMPLE_RULE: dict[str, str] = {
    "5m": "5min",
    "10m": "10min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    "2h": "2h",
    "3h": "3h",
}


def resample_candles(candles: list[dict[str, Any]], target_timeframe: str) -> list[dict[str, Any]]:
    """candles: ascending-time 5m OHLCV dicts (the shape MarketDataClient
    implementations return). Returns candles resampled to target_timeframe,
    dropping any trailing bucket with no bars in it.
    """
    if target_timeframe not in _RESAMPLE_RULE:
        raise ValueError(f"unsupported timeframe={target_timeframe!r}")
    if target_timeframe == "5m" or not candles:
        return candles

    timestamps = [c.get("date") or c["ts"] for c in candles]
    df = pd.DataFrame(candles, index=pd.DatetimeIndex(timestamps))
    resampled = (
        df.resample(_RESAMPLE_RULE[target_timeframe], label="left", closed="left")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna(subset=["open"])
    )

    return [
        {
            "date": ts.to_pydatetime(),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": int(row["volume"]),
        }
        for ts, row in resampled.iterrows()
    ]
