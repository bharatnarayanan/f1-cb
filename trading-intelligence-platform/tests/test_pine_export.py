"""Tests for src/engine/pine_export.py (F5.5)."""

import pytest

from src.engine.pine_export import export_to_pine_script

_CANONICAL_LOGIC = {
    "entry": {
        "logic": "AND",
        "conditions": [
            {"left": {"field": "close"}, "operator": ">", "right": {"indicator": "SMA", "period": 50}},
            {"left": {"field": "close"}, "operator": ">", "right": {"indicator": "VWAP", "period": 1}},
        ],
    },
    "exit": {
        "targets": [{"type": "prior_candle_high"}],
        "stop_loss": {"type": "below_ma", "reference_indicator": {"indicator": "SMA", "period": 50}},
    },
    "guards": [{"left": {"field": "close"}, "operator": ">", "right": {"indicator": "SUPERTREND", "period": 7, "params": {"multiplier": 3}}}],
}


def test_export_includes_version_and_strategy_declaration():
    script = export_to_pine_script(_CANONICAL_LOGIC, "My Strategy")

    assert "//@version=5" in script
    assert 'strategy("My Strategy"' in script


def test_export_translates_indicators():
    script = export_to_pine_script(_CANONICAL_LOGIC, "S")

    assert "ta.sma(close, 50)" in script
    assert "ta.vwap(close)" in script
    assert "ta.supertrend(3, 7)" in script


def test_export_joins_entry_conditions_with_and():
    script = export_to_pine_script(_CANONICAL_LOGIC, "S")

    assert "longCondition = " in script
    assert " and " in script


def test_export_includes_guard_in_entry_condition():
    script = export_to_pine_script(_CANONICAL_LOGIC, "S")

    line = next(line for line in script.splitlines() if line.startswith("longCondition"))
    assert "ta.supertrend" in line


def test_export_below_ma_stop_condition():
    script = export_to_pine_script(_CANONICAL_LOGIC, "S")

    assert "stopCondition = close < ta.sma(close, 50)" in script


def test_export_fixed_points_stop_leaves_a_comment_not_a_crash():
    canonical_logic = {**_CANONICAL_LOGIC, "exit": {**_CANONICAL_LOGIC["exit"], "stop_loss": {"type": "fixed_points", "value": 25}}}

    script = export_to_pine_script(canonical_logic, "S")

    assert "25" in script


def test_export_unsupported_indicator_raises():
    canonical_logic = {
        **_CANONICAL_LOGIC,
        "entry": {"logic": "AND", "conditions": [{"left": {"field": "close"}, "operator": ">", "right": {"indicator": "BOGUS", "period": 5}}]},
    }

    with pytest.raises(ValueError):
        export_to_pine_script(canonical_logic, "S")
