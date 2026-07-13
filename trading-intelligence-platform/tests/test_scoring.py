"""Tests for src/engine/scoring.py (F4.3)."""

import pytest

from src.engine.scoring import (
    SrContextLevel,
    compute_confidence,
    compute_conviction,
    compute_macro_sr_alignment,
    compute_risk,
    compute_rsi_alignment,
)


def test_macro_sr_alignment_neutral_with_no_levels():
    assert compute_macro_sr_alignment(100.0, "bullish", []) == 0.5


def test_macro_sr_alignment_full_room_when_no_adverse_level():
    levels = [SrContextLevel(level_price=95.0, level_type="support")]

    assert compute_macro_sr_alignment(100.0, "bullish", levels) == 1.0


def test_macro_sr_alignment_ratio_between_support_and_resistance():
    levels = [
        SrContextLevel(level_price=90.0, level_type="support"),      # 10 away
        SrContextLevel(level_price=130.0, level_type="resistance"),  # 30 away
    ]

    # adverse (resistance) is 3x farther than supportive (support) -> high score
    score = compute_macro_sr_alignment(100.0, "bullish", levels)

    assert score == pytest.approx(30 / (30 + 10), abs=1e-3)


def test_macro_sr_alignment_bearish_direction_flips_supportive_and_adverse():
    levels = [
        SrContextLevel(level_price=90.0, level_type="support"),      # adverse for bearish
        SrContextLevel(level_price=130.0, level_type="resistance"),  # supportive for bearish
    ]

    score = compute_macro_sr_alignment(100.0, "bearish", levels)

    assert score == pytest.approx(10 / (10 + 30), abs=1e-3)


def test_macro_sr_alignment_rejects_unknown_direction():
    with pytest.raises(ValueError):
        compute_macro_sr_alignment(100.0, "sideways", [])


def test_rsi_alignment_neutral_when_rsi_unavailable():
    assert compute_rsi_alignment(None, "bullish") == 0.5


def test_rsi_alignment_scales_with_distance_from_50():
    assert compute_rsi_alignment(75.0, "bullish") == pytest.approx(0.5)
    assert compute_rsi_alignment(100.0, "bullish") == 1.0
    assert compute_rsi_alignment(50.0, "bullish") == 0.0


def test_rsi_alignment_bearish_flips_direction():
    assert compute_rsi_alignment(25.0, "bearish") == pytest.approx(0.5)
    assert compute_rsi_alignment(0.0, "bearish") == 1.0


def test_rsi_alignment_zero_when_it_contradicts_direction():
    # Bullish pattern but RSI already deep oversold-side momentum -> no support.
    assert compute_rsi_alignment(20.0, "bullish") == 0.0


def test_compute_confidence_full_factors_sum_to_documented_weights():
    result = compute_confidence(
        macro_sr_alignment=1.0,
        heavyweight_pattern_alignment=1.0,
        rsi_alignment=1.0,
        strike_candle_pattern=1.0,
        oi_accumulation=1.0,
    )

    assert result["score"] == 100.0
    assert result["unavailable_factors"] == []


def test_compute_confidence_renormalizes_when_factors_missing():
    # Only the three available-in-this-phase factors, all maxed out.
    result = compute_confidence(macro_sr_alignment=1.0, heavyweight_pattern_alignment=1.0, rsi_alignment=1.0)

    assert result["score"] == 100.0  # renormalized weights still sum to 1.0
    assert set(result["unavailable_factors"]) == {"strike_candle_pattern", "oi_accumulation"}
    assert "strike_candle_pattern" not in result["factors"]


def test_compute_confidence_zero_factors_score_zero():
    result = compute_confidence(macro_sr_alignment=0.0, heavyweight_pattern_alignment=0.0, rsi_alignment=0.0)

    assert result["score"] == 0.0


def test_compute_confidence_requires_at_least_one_factor():
    with pytest.raises(ValueError):
        compute_confidence(macro_sr_alignment=None, heavyweight_pattern_alignment=None, rsi_alignment=None)


def test_compute_risk_scales_with_vix_regime():
    normal = compute_risk("normal")
    extreme = compute_risk("extreme")

    assert normal["score"] < extreme["score"]


def test_compute_risk_adds_expiry_and_liquidity_bumps():
    base = compute_risk("normal")
    bumped = compute_risk("normal", is_expiry_day=True, is_low_liquidity=True)

    assert bumped["score"] > base["score"]


def test_compute_risk_caps_at_100():
    result = compute_risk("extreme", is_expiry_day=True, is_low_liquidity=True)

    assert result["score"] <= 100.0


def test_compute_risk_rejects_unknown_regime():
    with pytest.raises(ValueError):
        compute_risk("bogus")


def test_compute_conviction_dampens_with_risk_but_never_zeroes_it():
    low_risk = compute_conviction(80.0, 20.0)
    high_risk = compute_conviction(80.0, 100.0)

    assert low_risk > high_risk
    assert high_risk == pytest.approx(80.0 * 0.5)  # max 50% dampening at risk=100
    assert high_risk > 0
