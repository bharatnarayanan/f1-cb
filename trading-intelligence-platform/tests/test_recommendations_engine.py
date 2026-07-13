"""Tests for src/engine/recommendations.py (F4.4, build_recommendation)."""

from datetime import datetime

import pytest

from src.engine.correlation import ConstituentMomentum
from src.engine.negation import predict_negation
from src.engine.recommendations import build_recommendation
from src.engine.scoring import SrContextLevel

_BAR_TS = datetime(2026, 7, 1, 9, 30)


def _negation_estimate():
    return predict_negation("engulfing", "15m", "normal", _BAR_TS)


def test_tactical_category_for_a_supported_timeframe():
    draft = build_recommendation(
        pattern_type="engulfing",
        direction="bullish",
        timeframe="15m",
        bar_ts=_BAR_TS,
        current_price=100.0,
        sr_levels=[],
        correlation_score=0.8,
        correlation_breakdown=[ConstituentMomentum(symbol="RELIANCE", direction="bullish")],
        rsi=65.0,
        vix_regime="normal",
        is_impulse=False,
        negation_estimate=_negation_estimate(),
    )

    assert draft.category == "tactical"
    assert draft.action == "BUY_CE"
    assert draft.forecast_horizon == "15m"
    assert 0 <= draft.confidence_score <= 100
    assert draft.rationale["narrative"] is None  # filled in later by the route, not here


def test_bearish_direction_maps_to_buy_pe():
    draft = build_recommendation(
        pattern_type="doji",
        direction="bearish",
        timeframe="1h",
        bar_ts=_BAR_TS,
        current_price=100.0,
        sr_levels=[],
        correlation_score=0.5,
        correlation_breakdown=[],
        rsi=None,
        vix_regime="elevated",
        is_impulse=False,
        negation_estimate=predict_negation("doji", "1h", "elevated", _BAR_TS),
    )

    assert draft.action == "BUY_PE"


def test_impulse_category_regardless_of_timeframe_label():
    draft = build_recommendation(
        pattern_type="impulse",
        direction="bullish",
        timeframe="5m",
        bar_ts=_BAR_TS,
        current_price=100.0,
        sr_levels=[],
        correlation_score=0.5,
        correlation_breakdown=[],
        rsi=60.0,
        vix_regime="normal",
        is_impulse=True,
        negation_estimate=predict_negation("impulse", "5m", "normal", _BAR_TS),
    )

    assert draft.category == "impulse"


def test_unsupported_timeframe_raises_rather_than_mislabeling():
    with pytest.raises(ValueError, match="Strategic|BTST"):
        build_recommendation(
            pattern_type="engulfing",
            direction="bullish",
            timeframe="1d",
            bar_ts=_BAR_TS,
            current_price=100.0,
            sr_levels=[],
            correlation_score=0.5,
            correlation_breakdown=[],
            rsi=None,
            vix_regime="normal",
            is_impulse=False,
            negation_estimate=_negation_estimate(),
        )


def test_unknown_direction_raises():
    with pytest.raises(ValueError):
        build_recommendation(
            pattern_type="engulfing",
            direction="sideways",
            timeframe="15m",
            bar_ts=_BAR_TS,
            current_price=100.0,
            sr_levels=[],
            correlation_score=0.5,
            correlation_breakdown=[],
            rsi=None,
            vix_regime="normal",
            is_impulse=False,
            negation_estimate=_negation_estimate(),
        )


def test_rationale_tree_has_the_expected_shape():
    draft = build_recommendation(
        pattern_type="engulfing",
        direction="bullish",
        timeframe="30m",
        bar_ts=_BAR_TS,
        current_price=100.0,
        sr_levels=[SrContextLevel(level_price=95.0, level_type="support")],
        correlation_score=0.6,
        correlation_breakdown=[ConstituentMomentum(symbol="TCS", direction="bullish")],
        rsi=55.0,
        vix_regime="high",
        is_impulse=False,
        negation_estimate=predict_negation("engulfing", "30m", "high", _BAR_TS),
    )

    for key in ("pattern", "negation", "correlation", "rsi", "confidence", "risk", "conviction_score", "narrative"):
        assert key in draft.rationale
    assert draft.rationale["correlation"]["constituents"][0]["symbol"] == "TCS"
