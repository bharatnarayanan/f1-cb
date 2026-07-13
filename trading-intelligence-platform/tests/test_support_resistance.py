"""Tests for src/engine/support_resistance.py (F3.4)."""

from datetime import datetime, timedelta

from src.engine.support_resistance import calculate_sr_levels

_START = datetime(2026, 7, 1, 9, 15)


def _candles(highs: list[float], lows: list[float]) -> list[dict]:
    return [
        {
            "date": _START + timedelta(minutes=5 * i),
            "open": (h + l) / 2,
            "high": h,
            "low": l,
            "close": (h + l) / 2,
            "volume": 1000,
        }
        for i, (h, l) in enumerate(zip(highs, lows))
    ]


def test_returns_empty_list_below_minimum_bar_count():
    candles = _candles([100, 101, 102], [98, 99, 100])

    assert calculate_sr_levels(candles) == []


def test_detects_repeated_resistance_level_with_full_confluence():
    block = [100, 101, 102, 103, 102, 101, 100]
    highs = block * 3  # three identical peaks at 103, spaced one block apart
    lows = [50] * len(highs)  # constant -> never a unique local min, no support noise

    levels = calculate_sr_levels(_candles(highs, lows))

    resistance = [lvl for lvl in levels if lvl.level_type == "resistance"]
    assert len(resistance) == 1
    assert resistance[0].level_price == 103.0
    assert resistance[0].hit_count == 3
    assert resistance[0].confluence_score == 1.0
    assert not [lvl for lvl in levels if lvl.level_type == "support"]


def test_detects_a_single_support_level():
    lows = [100, 99, 98, 97, 98, 99, 100]
    highs = [110] * len(lows)  # constant -> no resistance noise

    levels = calculate_sr_levels(_candles(highs, lows))

    support = [lvl for lvl in levels if lvl.level_type == "support"]
    assert len(support) == 1
    assert support[0].level_price == 97.0
    assert support[0].hit_count == 1
    assert support[0].confluence_score == 1.0


def test_clusters_nearby_resistance_touches_into_one_level():
    block1 = [100, 101, 102, 103.00, 102, 101, 100]
    block2 = [100, 101, 102, 103.02, 102, 101, 100]  # within default 0.1% tolerance of 103.00
    highs = block1 + block2
    lows = [50] * len(highs)

    levels = calculate_sr_levels(_candles(highs, lows))

    assert len(levels) == 1
    assert levels[0].hit_count == 2
    assert levels[0].level_price == round((103.00 + 103.02) / 2, 2)
