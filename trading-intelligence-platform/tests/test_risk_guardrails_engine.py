"""Tests for src/engine/risk_guardrails.py (Phase 8, F8.1) — pure functions."""

from datetime import date

from src.engine.risk_guardrails import (
    EXPIRY_DAY_CONVICTION_DAMPENING,
    apply_expiry_dampening,
    is_expiry_day,
    should_suppress_tactical,
)


def test_is_expiry_day_true_on_matching_weekday():
    # 2026-07-14 is a Tuesday (weekday=1).
    assert is_expiry_day(date(2026, 7, 14), expiry_weekday=1) is True


def test_is_expiry_day_false_on_other_weekdays():
    assert is_expiry_day(date(2026, 7, 15), expiry_weekday=1) is False


def test_should_suppress_tactical_true_when_all_conditions_met():
    assert should_suppress_tactical("tactical", "extreme", suppress_tactical_on_extreme=True) is True


def test_should_suppress_tactical_false_for_non_tactical_category():
    assert should_suppress_tactical("impulse", "extreme", suppress_tactical_on_extreme=True) is False


def test_should_suppress_tactical_false_when_regime_not_extreme():
    assert should_suppress_tactical("tactical", "high", suppress_tactical_on_extreme=True) is False


def test_should_suppress_tactical_false_when_setting_disabled():
    assert should_suppress_tactical("tactical", "extreme", suppress_tactical_on_extreme=False) is False


def test_apply_expiry_dampening_reduces_score_when_expiry_and_enabled():
    result = apply_expiry_dampening(50.0, is_expiry=True, expiry_day_dampening_enabled=True)
    assert result == round(50.0 * EXPIRY_DAY_CONVICTION_DAMPENING, 2)


def test_apply_expiry_dampening_unchanged_when_not_expiry():
    assert apply_expiry_dampening(50.0, is_expiry=False, expiry_day_dampening_enabled=True) == 50.0


def test_apply_expiry_dampening_unchanged_when_disabled():
    assert apply_expiry_dampening(50.0, is_expiry=True, expiry_day_dampening_enabled=False) == 50.0
