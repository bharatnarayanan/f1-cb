"""Tests for src/engine/aggregation.py (F3.3)."""

from datetime import datetime, timedelta

import pytest

from src.engine.aggregation import resample_candles

_START = datetime(2026, 7, 1, 9, 15)


def _candle(i: int, o: float, h: float, l: float, c: float, v: int) -> dict:
    return {"date": _START + timedelta(minutes=5 * i), "open": o, "high": h, "low": l, "close": c, "volume": v}


def test_5m_passthrough_is_a_noop():
    candles = [_candle(i, 100, 101, 99, 100, 1000) for i in range(3)]

    assert resample_candles(candles, "5m") == candles


def test_empty_input_returns_empty():
    assert resample_candles([], "15m") == []


def test_resamples_twelve_5m_candles_into_four_15m_buckets():
    # 12 bars * 5m = exactly four 15m buckets (3 bars each).
    candles = [_candle(i, 100 + i, 101 + i, 99 + i, 100.5 + i, 1000) for i in range(12)]

    resampled = resample_candles(candles, "15m")

    assert len(resampled) == 4
    first_bucket = resampled[0]
    assert first_bucket["date"] == _START
    assert first_bucket["open"] == candles[0]["open"]
    assert first_bucket["close"] == candles[2]["close"]
    assert first_bucket["high"] == max(c["high"] for c in candles[0:3])
    assert first_bucket["low"] == min(c["low"] for c in candles[0:3])
    assert first_bucket["volume"] == sum(c["volume"] for c in candles[0:3])


def test_unsupported_timeframe_raises():
    with pytest.raises(ValueError, match="timeframe"):
        resample_candles([_candle(0, 100, 101, 99, 100, 1000)], "9m")
