"""Tests for src/engine/fusion.py (F5.4)."""

import pytest

from src.engine.fusion import fuse_strategies

_BASE = {
    "version": "1.0",
    "instrument": {"underlying": "NIFTY", "leg": "either"},
    "timeframe": "15m",
    "entry": {"logic": "AND", "conditions": [{"left": {"field": "close"}, "operator": ">", "right": {"indicator": "SMA", "period": 50}}]},
    "exit": {
        "targets": [{"type": "prior_candle_high"}],
        "stop_loss": {"type": "below_ma", "reference_indicator": {"indicator": "SMA", "period": 50}},
    },
    "guards": [],
}

_OTHER = {
    "version": "1.0",
    "instrument": {"underlying": "NIFTY", "leg": "either"},
    "timeframe": "15m",
    "entry": {"logic": "AND", "conditions": [{"left": {"field": "close"}, "operator": ">", "right": {"indicator": "VWAP", "period": 1}}]},
    "exit": {
        "targets": [{"type": "day_high"}],
        "stop_loss": {"type": "below_vwap"},
    },
    "guards": [{"left": {"field": "close"}, "operator": ">", "right": 100}],
}


def test_fuse_unions_entry_conditions():
    fused = fuse_strategies(_BASE, _OTHER)

    assert len(fused["entry"]["conditions"]) == 2
    assert fused["entry"]["logic"] == "AND"


def test_fuse_unions_targets():
    fused = fuse_strategies(_BASE, _OTHER)

    target_types = {t["type"] for t in fused["exit"]["targets"]}
    assert target_types == {"prior_candle_high", "day_high"}


def test_fuse_keeps_base_stop_loss():
    fused = fuse_strategies(_BASE, _OTHER)

    assert fused["exit"]["stop_loss"] == _BASE["exit"]["stop_loss"]


def test_fuse_folds_other_stop_loss_into_guards():
    fused = fuse_strategies(_BASE, _OTHER)

    # other's below_vwap stop_loss becomes an extra "close > VWAP" guard.
    assert any(
        g["left"] == {"field": "close"} and g["operator"] == ">" and isinstance(g["right"], dict) and g["right"].get("indicator") == "VWAP"
        for g in fused["guards"]
    )
    # other's own explicit guard is also preserved.
    assert {"left": {"field": "close"}, "operator": ">", "right": 100} in fused["guards"]


def test_fuse_is_not_marked_a_preset():
    fused = fuse_strategies(_BASE, _OTHER)

    assert fused["is_preset"] is False


def test_fuse_rejects_mismatched_underlyings():
    other_bnf = {**_OTHER, "instrument": {"underlying": "BANKNIFTY", "leg": "either"}}

    with pytest.raises(ValueError, match="underlying"):
        fuse_strategies(_BASE, other_bnf)


def test_fuse_fixed_points_stop_not_expressible_as_guard():
    other_fixed = {**_OTHER, "exit": {**_OTHER["exit"], "stop_loss": {"type": "fixed_points", "value": 20}}}

    fused = fuse_strategies(_BASE, other_fixed)

    # fixed_points can't become a boolean guard — only other's explicit guard should be added.
    assert len(fused["guards"]) == len(_BASE["guards"]) + len(_OTHER["guards"])
