"""Tests for src/market_data/vix.py (compute_vix_regime).

Pure function, no I/O — threshold resolution (env vs. DB risk_settings
row) is tested separately in tests/test_risk_settings.py.
"""

from src.market_data.vix import compute_vix_regime

_THRESHOLDS = (15.0, 20.0, 30.0)


def test_normal_regime():
    assert compute_vix_regime(10.0, *_THRESHOLDS) == "normal"


def test_elevated_regime():
    assert compute_vix_regime(17.0, *_THRESHOLDS) == "elevated"


def test_high_regime():
    assert compute_vix_regime(25.0, *_THRESHOLDS) == "high"


def test_extreme_regime():
    assert compute_vix_regime(35.0, *_THRESHOLDS) == "extreme"


def test_boundary_values_are_exclusive_on_the_lower_regime():
    # value < threshold, not <=, so exactly-at-threshold rolls into the next regime up.
    assert compute_vix_regime(15.0, *_THRESHOLDS) == "elevated"
    assert compute_vix_regime(20.0, *_THRESHOLDS) == "high"
    assert compute_vix_regime(30.0, *_THRESHOLDS) == "extreme"


def test_custom_thresholds_are_honored():
    # A tighter founder-configured band (Pass 2b) should change classification.
    assert compute_vix_regime(12.0, 10.0, 20.0, 30.0) == "elevated"
