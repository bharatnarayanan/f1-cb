"""Tests for src/engine/indicators.py."""

from datetime import datetime, timedelta

from src.engine.indicators import compute_rsi

_START = datetime(2026, 7, 1, 9, 15)


def _candles(closes: list[float]) -> list[dict]:
    return [
        {"date": _START + timedelta(minutes=5 * i), "open": c, "high": c, "low": c, "close": c, "volume": 1000}
        for i, c in enumerate(closes)
    ]


def test_returns_none_below_lookback_floor():
    assert compute_rsi(_candles([100, 101, 102]), period=14) is None


def test_returns_high_rsi_on_a_steady_uptrend():
    closes = [100 + i for i in range(20)]

    rsi = compute_rsi(_candles(closes), period=14)

    assert rsi is not None
    assert rsi > 70  # a clean, uninterrupted uptrend should read overbought


def test_returns_low_rsi_on_a_steady_downtrend():
    closes = [100 - i for i in range(20)]

    rsi = compute_rsi(_candles(closes), period=14)

    assert rsi is not None
    assert rsi < 30
