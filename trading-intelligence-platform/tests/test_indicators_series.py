"""Tests for the full-series indicator functions in src/engine/indicators.py
(Phase 5's strategy interpreter needs these; compute_rsi's single-value
behavior is already covered by tests/test_indicators.py)."""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from src.engine.indicators import ema_series, macd_series, sma_series, supertrend_series, vwap_series

_START = datetime(2026, 7, 1, 9, 15)


def _df(closes: list[float], highs: list[float] | None = None, lows: list[float] | None = None, volumes: list[int] | None = None) -> pd.DataFrame:
    n = len(closes)
    highs = highs or [c + 0.5 for c in closes]
    lows = lows or [c - 0.5 for c in closes]
    volumes = volumes or [1000] * n
    idx = pd.DatetimeIndex([_START + timedelta(minutes=5 * i) for i in range(n)])
    return pd.DataFrame({"open": closes, "high": highs, "low": lows, "close": closes, "volume": volumes}, index=idx)


def test_sma_series_matches_manual_average():
    df = _df([1, 2, 3, 4, 5])

    result = sma_series(df, period=3)

    assert np.isnan(result.iloc[1])  # not enough bars yet
    assert result.iloc[2] == pytest.approx((1 + 2 + 3) / 3)
    assert result.iloc[4] == pytest.approx((3 + 4 + 5) / 3)


def test_ema_series_converges_toward_a_flat_price():
    df = _df([100.0] * 30)

    result = ema_series(df, period=10)

    assert result.iloc[-1] == pytest.approx(100.0, abs=0.01)


def test_vwap_series_is_between_low_and_high_of_cumulative_range():
    df = _df([100, 101, 99, 102, 98], volumes=[100, 200, 150, 300, 250])

    result = vwap_series(df)

    assert result.notna().all()
    assert result.min() >= df["low"].min()
    assert result.max() <= df["high"].max()


def test_vwap_series_handles_zero_volume_without_crashing():
    df = _df([100, 101, 102], volumes=[0, 0, 0])

    result = vwap_series(df)

    assert result.isna().all()


def test_macd_series_returns_a_series_aligned_to_the_dataframe():
    df = _df([100 + i * 0.5 for i in range(60)])

    result = macd_series(df, period=12, params={"slowperiod": 26, "signalperiod": 9})

    assert len(result) == len(df)
    assert result.index.equals(df.index)


def test_supertrend_series_returns_no_nans_after_warmup():
    np.random.seed(0)
    closes = list(100 + np.cumsum(np.random.normal(0, 0.5, 50)))
    df = _df(closes)

    result = supertrend_series(df, period=7, multiplier=3.0)

    assert len(result) == len(df)
    assert not result.iloc[10:].isna().any()


def test_supertrend_series_stays_below_price_in_a_clean_uptrend():
    closes = [100 + i for i in range(40)]
    df = _df(closes)

    result = supertrend_series(df, period=7, multiplier=3.0)

    # In an uninterrupted uptrend, SuperTrend should sit as support below price.
    assert (result.iloc[15:] <= df["close"].iloc[15:]).all()
