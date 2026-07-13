"""Tests for src/engine/paper_trading.py (F6.1)."""

from datetime import datetime, timedelta, timezone

import pytest

from src.engine.paper_trading import compute_pnl_pct, evaluate_exit, resolve_exit_rule
from src.engine.scoring import SrContextLevel

_NOW = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)


def test_resolve_exit_rule_bullish_uses_nearest_favorable_and_adverse_levels():
    levels = [
        SrContextLevel(level_price=110.0, level_type="resistance"),  # favorable, nearest
        SrContextLevel(level_price=130.0, level_type="resistance"),  # favorable, farther
        SrContextLevel(level_price=95.0, level_type="support"),      # adverse, nearest
        SrContextLevel(level_price=80.0, level_type="support"),      # adverse, farther
    ]

    rule = resolve_exit_rule("bullish", entry_price=100.0, sr_levels=levels)

    assert rule.target_price == 110.0
    assert rule.stop_loss_price == 95.0


def test_resolve_exit_rule_bearish_uses_nearest_favorable_and_adverse_levels():
    levels = [
        SrContextLevel(level_price=90.0, level_type="support"),      # favorable, nearest
        SrContextLevel(level_price=110.0, level_type="resistance"),  # adverse, nearest
    ]

    rule = resolve_exit_rule("bearish", entry_price=100.0, sr_levels=levels)

    assert rule.target_price == 90.0
    assert rule.stop_loss_price == 110.0


def test_resolve_exit_rule_falls_back_to_pct_band_when_no_levels():
    rule = resolve_exit_rule("bullish", entry_price=100.0, sr_levels=[])

    assert rule.target_price == pytest.approx(101.0)
    assert rule.stop_loss_price == pytest.approx(99.5)


def test_resolve_exit_rule_rejects_unknown_direction():
    with pytest.raises(ValueError):
        resolve_exit_rule("sideways", 100.0, [])


def test_evaluate_exit_bullish_target_hit():
    reason = evaluate_exit("bullish", current_price=111.0, target_price=110.0, stop_loss_price=95.0, now=_NOW, expiry_at=None)

    assert reason == "target"


def test_evaluate_exit_bullish_stop_hit():
    reason = evaluate_exit("bullish", current_price=94.0, target_price=110.0, stop_loss_price=95.0, now=_NOW, expiry_at=None)

    assert reason == "stop_loss"


def test_evaluate_exit_bearish_target_hit():
    reason = evaluate_exit("bearish", current_price=89.0, target_price=90.0, stop_loss_price=110.0, now=_NOW, expiry_at=None)

    assert reason == "target"


def test_evaluate_exit_expiry_hit_when_neither_level_reached():
    expiry = _NOW - timedelta(minutes=1)

    reason = evaluate_exit("bullish", current_price=101.0, target_price=110.0, stop_loss_price=95.0, now=_NOW, expiry_at=expiry)

    assert reason == "expiry"


def test_evaluate_exit_stays_open_when_nothing_triggered():
    expiry = _NOW + timedelta(hours=1)

    reason = evaluate_exit("bullish", current_price=101.0, target_price=110.0, stop_loss_price=95.0, now=_NOW, expiry_at=expiry)

    assert reason is None


def test_evaluate_exit_no_expiry_stays_open_indefinitely():
    reason = evaluate_exit("bullish", current_price=101.0, target_price=110.0, stop_loss_price=95.0, now=_NOW, expiry_at=None)

    assert reason is None


def test_compute_pnl_pct_bullish_profit():
    assert compute_pnl_pct("bullish", entry_price=100.0, exit_price=110.0) == 10.0


def test_compute_pnl_pct_bullish_loss():
    assert compute_pnl_pct("bullish", entry_price=100.0, exit_price=95.0) == -5.0


def test_compute_pnl_pct_bearish_profit_on_falling_price():
    assert compute_pnl_pct("bearish", entry_price=100.0, exit_price=90.0) == 10.0


def test_compute_pnl_pct_bearish_loss_on_rising_price():
    assert compute_pnl_pct("bearish", entry_price=100.0, exit_price=105.0) == -5.0
