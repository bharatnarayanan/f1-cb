"""Tests for src/engine/patterns.py (F3.1)."""

from datetime import datetime, timedelta

from src.engine.patterns import DetectedPattern, detect_patterns

_START = datetime(2026, 7, 1, 9, 15)

# Body (0.2) dominates the full range (0.4) so this filler candle is immune
# to both the doji check (body far above TA-Lib's ~10% average-body
# threshold) and the pin-bar check (body/range 0.5 > the 0.35 cap) — pure
# "nothing happening" bars so pattern assertions only match the bar we
# actually constructed to trigger.
_FILLER = {"open": 100.0, "high": 100.3, "low": 99.9, "close": 100.2}

# TA-Lib's doji-family functions need ~10 prior bars to establish their
# internal average-body baseline before they'll flag anything (see
# src/engine/patterns.py's _MIN_BARS_FOR_DETECTION comment) — 15 filler
# bars ahead of the bar under test covers that with margin.
_FILLER_COUNT = 15


def _candle(i: int, o: float, h: float, l: float, c: float, v: int = 10000) -> dict:
    return {"date": _START + timedelta(minutes=5 * i), "open": o, "high": h, "low": l, "close": c, "volume": v}


def _filler(i: int) -> dict:
    return _candle(i, _FILLER["open"], _FILLER["high"], _FILLER["low"], _FILLER["close"])


def _with_filler_prefix(*last_candles: dict) -> list[dict]:
    filler = [_filler(i) for i in range(_FILLER_COUNT)]
    offset = len(filler)
    shifted_last = []
    for j, candle in enumerate(last_candles):
        candle = dict(candle)
        candle["date"] = _START + timedelta(minutes=5 * (offset + j))
        shifted_last.append(candle)
    return filler + shifted_last


def test_returns_empty_list_below_minimum_bar_count():
    candles = [_filler(i) for i in range(14)]  # one below the floor

    assert detect_patterns(candles) == []


def test_detects_bullish_engulfing():
    candles = _with_filler_prefix(
        {"open": 100.0, "high": 101.0, "low": 98.0, "close": 99.0},   # small bearish body
        {"open": 98.5, "high": 103.0, "low": 98.0, "close": 102.0},   # engulfs the bar above
    )

    detected = detect_patterns(candles)

    engulfing = [p for p in detected if p.pattern_type == "engulfing"]
    assert len(engulfing) == 1
    assert engulfing[0].direction == "bullish"
    assert engulfing[0].bar_ts == candles[-1]["date"]


def test_detects_doji():
    candles = _with_filler_prefix({"open": 100.0, "high": 102.0, "low": 98.0, "close": 100.0})

    detected = detect_patterns(candles)

    assert any(p.pattern_type == "doji" and p.bar_ts == candles[-1]["date"] for p in detected)


def test_detects_bullish_pin_bar():
    candles = _with_filler_prefix({"open": 100.0, "high": 100.6, "low": 97.0, "close": 100.5})

    detected = detect_patterns(candles)

    pin_bars = [p for p in detected if p.pattern_type == "pin_bar"]
    assert len(pin_bars) == 1
    assert pin_bars[0].direction == "bullish"
    assert pin_bars[0].bar_ts == candles[-1]["date"]


def test_detects_bearish_pin_bar():
    candles = _with_filler_prefix({"open": 100.0, "high": 103.0, "low": 99.4, "close": 100.1})

    detected = detect_patterns(candles)

    pin_bars = [p for p in detected if p.pattern_type == "pin_bar"]
    assert len(pin_bars) == 1
    assert pin_bars[0].direction == "bearish"
    assert pin_bars[0].bar_ts == candles[-1]["date"]


def test_returns_detected_pattern_instances():
    candles = _with_filler_prefix(
        {"open": 100.0, "high": 101.0, "low": 98.0, "close": 99.0},
        {"open": 98.5, "high": 103.0, "low": 98.0, "close": 102.0},
    )

    detected = detect_patterns(candles)

    assert detected
    assert all(isinstance(p, DetectedPattern) for p in detected)
