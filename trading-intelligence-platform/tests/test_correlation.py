"""Tests for src/engine/correlation.py (F4.1)."""

from datetime import datetime, timedelta

from src.engine.correlation import momentum_direction, score_correlation

_START = datetime(2026, 7, 1, 9, 15)


def _candles(closes: list[float]) -> list[dict]:
    return [
        {"date": _START + timedelta(minutes=5 * i), "open": c, "high": c, "low": c, "close": c, "volume": 1000}
        for i, c in enumerate(closes)
    ]


def test_momentum_direction_bullish_on_rising_closes():
    assert momentum_direction(_candles([100, 100, 100, 100, 100, 105]), lookback=5) == "bullish"


def test_momentum_direction_bearish_on_falling_closes():
    assert momentum_direction(_candles([100, 100, 100, 100, 100, 95]), lookback=5) == "bearish"


def test_momentum_direction_flat_when_unchanged():
    assert momentum_direction(_candles([100, 100, 100, 100, 100, 100]), lookback=5) == "flat"


def test_momentum_direction_flat_on_insufficient_data():
    assert momentum_direction(_candles([100, 101]), lookback=5) == "flat"


def test_score_correlation_full_agreement():
    constituents = {
        "A": _candles([100, 100, 100, 100, 100, 105]),
        "B": _candles([100, 100, 100, 100, 100, 110]),
    }

    score, breakdown = score_correlation("bullish", constituents)

    assert score == 1.0
    assert len(breakdown) == 2


def test_score_correlation_partial_agreement():
    constituents = {
        "A": _candles([100, 100, 100, 100, 100, 105]),  # bullish, agrees
        "B": _candles([100, 100, 100, 100, 100, 95]),   # bearish, disagrees
    }

    score, _ = score_correlation("bullish", constituents)

    assert score == 0.5


def test_score_correlation_excludes_flat_constituents_from_denominator():
    constituents = {
        "A": _candles([100, 100, 100, 100, 100, 105]),  # bullish, agrees
        "B": _candles([100, 100, 100, 100, 100, 100]),  # flat, excluded
    }

    score, _ = score_correlation("bullish", constituents)

    assert score == 1.0


def test_score_correlation_returns_zero_when_nothing_decisive():
    constituents = {"A": _candles([100, 100, 100, 100, 100, 100])}

    score, breakdown = score_correlation("bullish", constituents)

    assert score == 0.0
    assert breakdown[0].direction == "flat"
