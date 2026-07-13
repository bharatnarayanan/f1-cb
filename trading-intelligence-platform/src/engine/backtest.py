"""Independent backtest engine (F5.3) — wraps vectorbt (docs/CLAUDE.md
section 4: "do NOT build a backtest engine from scratch"). Interprets
canonical_logic via src/engine/strategy_interpreter.py, simulates a
long-only position against fetched candles, and derives a documented 0-100
confidence score from the resulting trade statistics.

Backtest assumptions, documented per docs/CLAUDE.md section 6:
- Long-only simulation on the underlying's close price — a proxy for
  buying the declared option leg, not real option premium/greeks P&L
  (see src/engine/strategy_interpreter.py's module docstring).
- fixed_points targets/stops are converted to a percentage using the
  FIRST candle's close in the fetched window as the reference price
  (vectorbt's sl_stop/tp_stop are percentage-of-entry-price, not absolute
  points) — an approximation, not exact, most defensible when price
  doesn't move far from that reference across the backtest window.
- No commissions or slippage are modeled (vectorbt supports both `fees`
  and `slippage` params; neither is set here) — idealized fills, exactly
  the kind of thing docs/CLAUDE.md section 6 says backtests must not
  present as reality without saying so. Flagged here, not hidden.
- confidence_score's formula is new and documented (no formula exists
  anywhere in the original spec, same posture as Phase 4's
  conviction_score): a blend of win rate, a capped Sharpe ratio, and
  drawdown severity, scaled down for a thin trade sample (fewer than 20
  trades is weak evidence either way).
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import vectorbt as vbt

from src.engine.strategy_interpreter import (
    compute_entry_signal,
    compute_exit_signal,
    has_fixed_points_stop,
    has_fixed_points_target,
)

MIN_CANDLES_FOR_BACKTEST = 30
_MIN_TRADES_FOR_FULL_CONFIDENCE = 20


@dataclass(frozen=True)
class BacktestResult:
    num_trades: int
    win_rate_pct: float | None
    sharpe_ratio: float | None
    max_drawdown_pct: float | None
    total_return_pct: float | None
    confidence_score: float
    trade_log: list[dict[str, Any]]
    assumptions: list[str]


_ASSUMPTIONS = [
    "Long-only simulation on the underlying's close price — a proxy for the option leg, not real premium/greeks P&L.",
    "fixed_points targets/stops are converted to a percentage using the first candle's close as the reference price.",
    "No commissions or slippage are modeled — idealized fills.",
    "Exit decisions are made on bar close only, never intrabar high/low.",
]


def _candles_to_df(candles: list[dict[str, Any]]) -> pd.DataFrame:
    timestamps = [c.get("date") or c["ts"] for c in candles]
    df = pd.DataFrame(candles)
    df.index = pd.DatetimeIndex(timestamps)
    return df


def _compute_confidence(num_trades: int, win_rate_fraction: float | None, sharpe: float | None, max_drawdown_pct: float | None) -> float:
    if num_trades == 0 or win_rate_fraction is None:
        return 0.0

    win_component = win_rate_fraction
    sharpe_component = 0.5 if sharpe is None or np.isnan(sharpe) else max(0.0, min(1.0, sharpe / 3.0))
    drawdown_component = 1.0 if max_drawdown_pct is None else max(0.0, 1.0 - abs(max_drawdown_pct) / 50.0)

    raw = 0.5 * win_component + 0.3 * sharpe_component + 0.2 * drawdown_component
    sample_size_factor = min(1.0, num_trades / _MIN_TRADES_FOR_FULL_CONFIDENCE)
    return round(raw * sample_size_factor * 100, 2)


def run_backtest(canonical_logic: dict[str, Any], candles: list[dict[str, Any]]) -> BacktestResult:
    if len(candles) < MIN_CANDLES_FOR_BACKTEST:
        raise ValueError(f"need at least {MIN_CANDLES_FOR_BACKTEST} candles to run a backtest, got {len(candles)}")

    df = _candles_to_df(candles)
    entries = compute_entry_signal(canonical_logic, df)
    exits = compute_exit_signal(canonical_logic, df) & ~entries

    reference_price = float(df["close"].iloc[0])
    fixed_target_points = has_fixed_points_target(canonical_logic)
    fixed_stop_points = has_fixed_points_stop(canonical_logic)
    tp_stop = (fixed_target_points / reference_price) if fixed_target_points else None
    sl_stop = (fixed_stop_points / reference_price) if fixed_stop_points else None

    freq = pd.infer_freq(df.index) or "5min"
    portfolio = vbt.Portfolio.from_signals(
        df["close"], entries, exits,
        sl_stop=sl_stop, tp_stop=tp_stop,
        direction="longonly",
        freq=freq,
        init_cash=100_000,
    )

    trades = portfolio.trades
    num_trades = len(trades.records_readable)

    win_rate_fraction = float(trades.win_rate()) if num_trades > 0 else None
    sharpe = float(portfolio.sharpe_ratio()) if num_trades > 0 else None
    sharpe = None if sharpe is not None and np.isnan(sharpe) else sharpe
    max_dd_pct = float(portfolio.max_drawdown()) * 100 if num_trades > 0 else None
    total_return_pct = float(portfolio.total_return()) * 100 if num_trades > 0 else None

    trade_log = []
    if num_trades > 0:
        for _, row in trades.records_readable.iterrows():
            trade_log.append(
                {
                    "entry_ts": str(row["Entry Timestamp"]),
                    "exit_ts": str(row["Exit Timestamp"]),
                    "entry_price": round(float(row["Avg Entry Price"]), 2),
                    "exit_price": round(float(row["Avg Exit Price"]), 2),
                    "pnl": round(float(row["PnL"]), 2),
                    "return_pct": round(float(row["Return"]) * 100, 2),
                }
            )

    return BacktestResult(
        num_trades=num_trades,
        win_rate_pct=round(win_rate_fraction * 100, 2) if win_rate_fraction is not None else None,
        sharpe_ratio=round(sharpe, 4) if sharpe is not None else None,
        max_drawdown_pct=round(max_dd_pct, 2) if max_dd_pct is not None else None,
        total_return_pct=round(total_return_pct, 2) if total_return_pct is not None else None,
        confidence_score=_compute_confidence(num_trades, win_rate_fraction, sharpe, max_dd_pct),
        trade_log=trade_log,
        assumptions=_ASSUMPTIONS,
    )
