"""Tests for src/engine/negation.py (F3.2)."""

from datetime import datetime

import pytest

from src.engine.negation import MODEL_VERSION, predict_negation

_BAR_TS = datetime(2026, 7, 1, 9, 15)


def test_predicts_expected_candles_and_window_for_normal_regime():
    estimate = predict_negation("engulfing", "5m", "normal", _BAR_TS)

    assert estimate.predicted_candles == 3.0  # base=3.0 * multiplier=1.0
    assert estimate.predicted_window_start == _BAR_TS
    assert estimate.model_version == MODEL_VERSION


def test_higher_vix_regime_shortens_the_predicted_window():
    normal = predict_negation("engulfing", "5m", "normal", _BAR_TS)
    extreme = predict_negation("engulfing", "5m", "extreme", _BAR_TS)

    assert extreme.predicted_candles < normal.predicted_candles
    assert extreme.predicted_window_end < normal.predicted_window_end


def test_window_end_scales_with_timeframe_duration():
    five_min = predict_negation("doji", "5m", "normal", _BAR_TS)
    one_hour = predict_negation("doji", "1h", "normal", _BAR_TS)

    # Same candle count, but each 1h bar spans 12x a 5m bar.
    assert five_min.predicted_candles == one_hour.predicted_candles
    five_min_minutes = (five_min.predicted_window_end - _BAR_TS).total_seconds() / 60
    one_hour_minutes = (one_hour.predicted_window_end - _BAR_TS).total_seconds() / 60
    assert one_hour_minutes == pytest.approx(five_min_minutes * 12)


def test_unknown_pattern_type_raises():
    with pytest.raises(ValueError, match="pattern_type"):
        predict_negation("bogus", "5m", "normal", _BAR_TS)


def test_unknown_vix_regime_raises():
    with pytest.raises(ValueError, match="vix_regime"):
        predict_negation("engulfing", "5m", "bogus", _BAR_TS)


def test_unknown_timeframe_raises():
    with pytest.raises(ValueError, match="timeframe"):
        predict_negation("engulfing", "9m", "normal", _BAR_TS)
