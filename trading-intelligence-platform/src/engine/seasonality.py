"""Intraday seasonality + impulse-move detection (F4.2).

Seasonality windows are fixed IST scan times (10:00, 11:00, 12:30 EU-open
proxy, 13:30, 14:00, 14:30-15:00 — docs/assumptions.md #9), stored in
`seasonality_windows` (seeded by alembic/versions/0001_initial_schema.py)
so they're runtime-configurable, not hardcoded here. This module is
DB-agnostic on purpose (docs/CLAUDE.md's "small, testable modules"
convention) — callers fetch the window rows and pass them in.

Impulse-move detection flags a bar whose range is a volatility outlier
relative to its own recent history — a deterministic statistical check
(docs/CLAUDE.md section 3), not a pattern-recognition call.
"""

from dataclasses import dataclass
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

_DEFAULT_IMPULSE_LOOKBACK = 20
_DEFAULT_IMPULSE_THRESHOLD_MULTIPLIER = 3.0


def in_seasonality_window(ts: datetime, windows: list[tuple[str, time, time]]) -> str | None:
    """ts: any timezone-aware datetime (converted to IST for comparison).
    windows: (label, window_start, window_end) tuples, IST wall-clock times.
    Returns the matching window's label, or None if ts falls in no window.
    """
    ist_time = ts.astimezone(IST).time()
    for label, window_start, window_end in windows:
        if window_start <= ist_time <= window_end:
            return label
    return None


@dataclass(frozen=True)
class ImpulseMove:
    bar_ts: datetime
    direction: str  # "bullish" | "bearish"
    range_ratio: float  # this bar's range / the recent average range


def detect_impulse_move(
    candles: list[dict[str, Any]],
    lookback: int = _DEFAULT_IMPULSE_LOOKBACK,
    threshold_multiplier: float = _DEFAULT_IMPULSE_THRESHOLD_MULTIPLIER,
) -> ImpulseMove | None:
    """Flags the LAST candle only if its high-low range is at least
    threshold_multiplier times the average range of the `lookback` candles
    before it — an outlier-sized move, not just "a big-ish candle."
    """
    if len(candles) < lookback + 1:
        return None

    history = candles[-(lookback + 1) : -1]
    avg_range = sum(c["high"] - c["low"] for c in history) / len(history)
    if avg_range <= 0:
        return None

    last = candles[-1]
    last_range = last["high"] - last["low"]
    ratio = last_range / avg_range
    if ratio < threshold_multiplier:
        return None

    direction = "bullish" if last["close"] >= last["open"] else "bearish"
    bar_ts = last.get("date") or last["ts"]
    return ImpulseMove(bar_ts=bar_ts, direction=direction, range_ratio=round(ratio, 2))
