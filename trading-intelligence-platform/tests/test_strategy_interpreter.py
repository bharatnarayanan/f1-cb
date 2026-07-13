"""Tests for src/engine/strategy_interpreter.py (Phase 5)."""

from datetime import datetime, timedelta

import pandas as pd
import pytest

from src.engine.strategy_interpreter import (
    compute_entry_signal,
    compute_exit_signal,
    evaluate_condition,
    evaluate_conditions,
    has_fixed_points_stop,
    has_fixed_points_target,
    resolve_operand,
)

_START = datetime(2026, 7, 1, 9, 15)


def _df(closes: list[float]) -> pd.DataFrame:
    n = len(closes)
    idx = pd.DatetimeIndex([_START + timedelta(minutes=5 * i) for i in range(n)])
    return pd.DataFrame(
        {"open": closes, "high": [c + 1 for c in closes], "low": [c - 1 for c in closes], "close": closes, "volume": [1000] * n},
        index=idx,
    )


def test_resolve_operand_literal():
    assert resolve_operand(42, _df([1, 2, 3])) == 42.0


def test_resolve_operand_price_field():
    df = _df([1, 2, 3])
    result = resolve_operand({"field": "close"}, df)
    assert list(result) == [1, 2, 3]


def test_resolve_operand_unknown_field_raises():
    with pytest.raises(ValueError, match="field"):
        resolve_operand({"field": "bogus"}, _df([1, 2, 3]))


def test_resolve_operand_unknown_indicator_raises():
    with pytest.raises(ValueError, match="indicator"):
        resolve_operand({"indicator": "BOGUS", "period": 5}, _df([1, 2, 3]))


def test_resolve_operand_malformed_raises():
    with pytest.raises(ValueError, match="malformed"):
        resolve_operand({"nonsense": True}, _df([1, 2, 3]))


def test_evaluate_condition_simple_comparison():
    df = _df([10, 20, 5])
    condition = {"left": {"field": "close"}, "operator": ">", "right": 15}

    result = evaluate_condition(condition, df)

    assert list(result) == [False, True, False]


def test_evaluate_conditions_and_logic():
    df = _df([10, 20, 30])
    conditions = [
        {"left": {"field": "close"}, "operator": ">", "right": 15},
        {"left": {"field": "close"}, "operator": "<", "right": 25},
    ]

    result = evaluate_conditions(conditions, "AND", df)

    assert list(result) == [False, True, False]


def test_evaluate_conditions_or_logic():
    df = _df([10, 20, 30])
    conditions = [
        {"left": {"field": "close"}, "operator": "<", "right": 15},
        {"left": {"field": "close"}, "operator": ">", "right": 25},
    ]

    result = evaluate_conditions(conditions, "OR", df)

    assert list(result) == [True, False, True]


def test_evaluate_conditions_requires_at_least_one():
    with pytest.raises(ValueError):
        evaluate_conditions([], "AND", _df([1, 2, 3]))


def test_compute_entry_signal_applies_guards():
    df = _df([10, 20, 30])
    canonical_logic = {
        "entry": {"logic": "AND", "conditions": [{"left": {"field": "close"}, "operator": ">", "right": 5}]},
        "guards": [{"left": {"field": "close"}, "operator": ">", "right": 25}],
    }

    result = compute_entry_signal(canonical_logic, df)

    # entry condition alone is True for all 3 bars, but the guard restricts to bar 2 only.
    assert list(result) == [False, False, True]


def test_compute_exit_signal_prior_candle_high():
    df = _df([10, 20, 15])
    canonical_logic = {
        "exit": {
            "targets": [{"type": "prior_candle_high"}],
            "stop_loss": {"type": "fixed_points", "value": 5},
        }
    }

    result = compute_exit_signal(canonical_logic, df)

    # bar 2's close (15) vs bar 1's high (21) -> not hit; bar 1's close (20) vs bar 0's high (11) -> hit
    assert result.iloc[1] == True  # noqa: E712
    assert result.iloc[0] == False  # noqa: E712 (no prior bar)


def test_compute_exit_signal_below_ma_stop_loss():
    df = _df([100] * 15 + [50])  # sharp drop on the last bar
    canonical_logic = {
        "exit": {
            "targets": [{"type": "fixed_points", "value": 1000}],  # never hit, keeps this test isolated to the stop
            "stop_loss": {"type": "below_ma", "reference_indicator": {"indicator": "SMA", "period": 10}},
        }
    }

    result = compute_exit_signal(canonical_logic, df)

    assert result.iloc[-1] == True  # noqa: E712


def test_has_fixed_points_target_and_stop():
    canonical_logic = {
        "exit": {
            "targets": [{"type": "prior_candle_high"}, {"type": "fixed_points", "value": 40}],
            "stop_loss": {"type": "fixed_points", "value": 20},
        }
    }

    assert has_fixed_points_target(canonical_logic) == 40
    assert has_fixed_points_stop(canonical_logic) == 20


def test_has_fixed_points_returns_none_when_absent():
    canonical_logic = {
        "exit": {
            "targets": [{"type": "prior_candle_high"}],
            "stop_loss": {"type": "below_ma", "reference_indicator": {"indicator": "SMA", "period": 10}},
        }
    }

    assert has_fixed_points_target(canonical_logic) is None
    assert has_fixed_points_stop(canonical_logic) is None
