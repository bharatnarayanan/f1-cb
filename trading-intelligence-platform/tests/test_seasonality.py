"""Tests for src/engine/seasonality.py (F4.2)."""

from datetime import datetime, time, timedelta, timezone

from src.engine.seasonality import detect_impulse_move, in_seasonality_window

_WINDOWS = [
    ("10:00 scan", time(10, 0), time(10, 15)),
    ("EU open proxy", time(12, 30), time(12, 45)),
]


def test_in_seasonality_window_matches_ist_time():
    # 04:35 UTC == 10:05 IST (UTC+5:30) — inside the 10:00-10:15 window.
    ts = datetime(2026, 7, 1, 4, 35, tzinfo=timezone.utc)

    assert in_seasonality_window(ts, _WINDOWS) == "10:00 scan"


def test_in_seasonality_window_returns_none_outside_any_window():
    ts = datetime(2026, 7, 1, 3, 0, tzinfo=timezone.utc)  # 08:30 IST

    assert in_seasonality_window(ts, _WINDOWS) is None


def test_in_seasonality_window_converts_non_utc_input():
    # Already IST-labeled input should still work via astimezone.
    ist = timezone(timedelta(hours=5, minutes=30))
    ts = datetime(2026, 7, 1, 12, 35, tzinfo=ist)

    assert in_seasonality_window(ts, _WINDOWS) == "EU open proxy"


_START = datetime(2026, 7, 1, 9, 15)


def _candle(i: int, o: float, h: float, l: float, c: float) -> dict:
    return {"date": _START + timedelta(minutes=5 * i), "open": o, "high": h, "low": l, "close": c, "volume": 1000}


def test_detect_impulse_move_flags_an_outlier_range_bar():
    history = [_candle(i, 100, 100.2, 99.8, 100) for i in range(20)]  # range 0.4 each
    impulse_bar = _candle(20, 100, 103.0, 100.0, 102.5)  # range 3.0, ~7.5x average
    candles = history + [impulse_bar]

    impulse = detect_impulse_move(candles)

    assert impulse is not None
    assert impulse.direction == "bullish"
    assert impulse.range_ratio >= 3.0


def test_detect_impulse_move_returns_none_for_ordinary_bars():
    candles = [_candle(i, 100, 100.2, 99.8, 100) for i in range(25)]

    assert detect_impulse_move(candles) is None


def test_detect_impulse_move_returns_none_below_lookback_floor():
    candles = [_candle(i, 100, 103, 97, 102) for i in range(5)]

    assert detect_impulse_move(candles, lookback=20) is None
