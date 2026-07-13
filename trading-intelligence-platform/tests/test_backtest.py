"""Tests for src/engine/backtest.py (F5.3).

Uses the real seeded BVWR-shaped canonical_logic against real sample-mode
candles (via a fresh SampleMarketDataClient, no live network) — this is the
same interpreter+vectorbt pipeline the /strategies/{id}/backtest route runs,
verified end-to-end rather than only through mocks.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.engine.backtest import MIN_CANDLES_FOR_BACKTEST, run_backtest
from src.market_data.sample_client import SampleMarketDataClient

_BVWR_CANONICAL_LOGIC = {
    "version": "1.0",
    "instrument": {"underlying": "NIFTY", "leg": "either", "moneyness": "ITM", "price_band": {"min": 350, "max": 450}},
    "timeframe": "10m",
    "entry": {
        "logic": "AND",
        "conditions": [
            {"left": {"field": "close"}, "operator": ">", "right": {"indicator": "SMA", "period": 50}},
            {"left": {"field": "close"}, "operator": ">", "right": {"indicator": "VWAP", "period": 1}},
            {"left": {"field": "close"}, "operator": ">", "right": {"indicator": "SUPERTREND", "period": 7, "params": {"multiplier": 3}}},
        ],
    },
    "exit": {
        "targets": [{"type": "prior_candle_high"}, {"type": "day_high"}, {"type": "supertrend_line"}],
        "stop_loss": {"type": "below_ma", "reference_indicator": {"indicator": "SMA", "period": 50}},
    },
    "guards": [{"left": {"field": "close"}, "operator": ">", "right": {"indicator": "SMA", "period": 50}}],
}


def _sample_candles(count_days: int = 5, seed: int = 42) -> list[dict]:
    client = SampleMarketDataClient(seed=seed)
    to_date = datetime.now(timezone.utc)
    from_date = to_date - timedelta(days=count_days)
    return client.get_historical_candles(256265, "5minute", from_date, to_date)


def test_run_backtest_against_real_sample_candles():
    candles = _sample_candles()

    result = run_backtest(_BVWR_CANONICAL_LOGIC, candles)

    assert result.num_trades >= 0
    if result.num_trades > 0:
        assert 0 <= result.win_rate_pct <= 100
        assert result.max_drawdown_pct <= 0
        assert len(result.trade_log) == result.num_trades
    assert 0 <= result.confidence_score <= 100
    assert result.assumptions  # documented, never silently omitted


def test_run_backtest_rejects_too_few_candles():
    with pytest.raises(ValueError, match=str(MIN_CANDLES_FOR_BACKTEST)):
        run_backtest(_BVWR_CANONICAL_LOGIC, _sample_candles()[: MIN_CANDLES_FOR_BACKTEST - 1])


def test_run_backtest_zero_trades_when_entry_never_fires():
    candles = _sample_candles()
    impossible_logic = {
        **_BVWR_CANONICAL_LOGIC,
        "entry": {"logic": "AND", "conditions": [{"left": {"field": "close"}, "operator": "<", "right": -1}]},
    }

    result = run_backtest(impossible_logic, candles)

    assert result.num_trades == 0
    assert result.confidence_score == 0.0
    assert result.win_rate_pct is None
    assert result.trade_log == []


def test_run_backtest_fixed_points_stop_and_target_do_not_crash():
    candles = _sample_candles()
    fixed_points_logic = {
        **_BVWR_CANONICAL_LOGIC,
        "exit": {
            "targets": [{"type": "fixed_points", "value": 100}],
            "stop_loss": {"type": "fixed_points", "value": 50},
        },
    }

    result = run_backtest(fixed_points_logic, candles)

    assert result.num_trades >= 0
