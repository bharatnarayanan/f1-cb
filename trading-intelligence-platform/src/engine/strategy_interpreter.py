"""Interprets docs/strategy_schema.json's canonical_logic against real
candle data (F5.3's backtest engine consumes this).

canonical_logic never contains arbitrary code — docs/strategy_schema.json's
`operand` definition restricts every reference to a fixed vocabulary of
price fields and known indicators. This module maps that vocabulary onto
real pandas Series computed from candle data; it cannot execute anything
outside that fixed set (an unknown field/indicator/operator raises loudly
rather than silently doing nothing).

Backtest simplifications, documented per docs/CLAUDE.md section 6 ("must
document assumptions... no look-ahead bias"):
- LONG-only: entries are always a long position on the underlying's price
  series, a proxy for buying the declared option leg (CE/PE) — no real
  option premium/greeks/time-decay simulation exists yet.
- Exit decisions are made on bar CLOSE only, never intrabar high/low — no
  look-ahead into a bar's own future range.
- "day_high"/"day_low" targets are an expanding max/min over the whole
  fetched window, not a true session-reset high/low — this codebase
  doesn't track session boundaries yet (docs/assumptions.md).
"""

import operator
from typing import Any, Callable

import pandas as pd

from src.engine.indicators import ema_series, macd_series, rsi_series, sma_series, supertrend_series, vwap_series

_OPERATORS: dict[str, Callable[[Any, Any], Any]] = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
    "!=": operator.ne,
}

_INDICATOR_BUILDERS: dict[str, Callable[[pd.DataFrame, int, dict], pd.Series]] = {
    "SMA": lambda df, period, params: sma_series(df, period),
    "EMA": lambda df, period, params: ema_series(df, period),
    "RSI": lambda df, period, params: rsi_series(df, period),
    "MACD": lambda df, period, params: macd_series(df, period, params),
    "VWAP": lambda df, period, params: vwap_series(df),
    "SUPERTREND": lambda df, period, params: supertrend_series(df, period, params.get("multiplier", 3.0)),
}

# Target/stop_loss types resolved via vectorbt's native entry-relative
# stops (src/engine/backtest.py), not as a level series here — they need
# the actual per-trade entry price, which this module doesn't track.
FIXED_POINTS_TARGET_TYPE = "fixed_points"


def resolve_operand(operand: Any, df: pd.DataFrame) -> pd.Series | float:
    if isinstance(operand, (int, float)):
        return float(operand)
    if "field" in operand:
        if operand["field"] not in df.columns:
            raise ValueError(f"unknown price field={operand['field']!r}")
        return df[operand["field"]]
    if "indicator" in operand:
        builder = _INDICATOR_BUILDERS.get(operand["indicator"])
        if builder is None:
            raise ValueError(f"unsupported indicator={operand['indicator']!r}")
        return builder(df, operand["period"], operand.get("params", {}))
    raise ValueError(f"malformed operand: {operand!r}")


def evaluate_condition(condition: dict, df: pd.DataFrame) -> pd.Series:
    left = resolve_operand(condition["left"], df)
    right = resolve_operand(condition["right"], df)
    op = _OPERATORS.get(condition["operator"])
    if op is None:
        raise ValueError(f"unsupported operator={condition['operator']!r}")

    result = op(left, right)
    if isinstance(result, bool):  # both operands were literals
        return pd.Series(result, index=df.index)
    return result.fillna(False)


def evaluate_conditions(conditions: list[dict], logic: str, df: pd.DataFrame) -> pd.Series:
    if not conditions:
        raise ValueError("at least one condition is required")
    combined = evaluate_condition(conditions[0], df)
    for condition in conditions[1:]:
        series = evaluate_condition(condition, df)
        combined = (combined & series) if logic == "AND" else (combined | series)
    return combined


def compute_entry_signal(canonical_logic: dict, df: pd.DataFrame) -> pd.Series:
    entry = canonical_logic["entry"]
    signal = evaluate_conditions(entry["conditions"], entry.get("logic", "AND"), df)
    for guard in canonical_logic.get("guards", []):
        signal = signal & evaluate_condition(guard, df)
    return signal


def _resolve_target_level(target: dict, df: pd.DataFrame, sr_target_price: float | None) -> pd.Series | None:
    target_type = target.get("type")
    if target_type == "prior_candle_high":
        return df["high"].shift(1)
    if target_type == "prior_candle_low":
        return df["low"].shift(1)
    if target_type == "day_high":
        return df["high"].expanding().max()
    if target_type == "day_low":
        return df["low"].expanding().min()
    if target_type == "supertrend_line":
        return supertrend_series(df)
    if target_type == "sr_level":
        if sr_target_price is None:
            return None
        return pd.Series(sr_target_price, index=df.index)
    if target_type == FIXED_POINTS_TARGET_TYPE:
        return None  # handled by src/engine/backtest.py via vectorbt's tp_stop
    raise ValueError(f"unsupported exit target type={target_type!r}")


def _resolve_stop_level(stop_loss: dict, df: pd.DataFrame) -> pd.Series | None:
    stop_type = stop_loss.get("type")
    if stop_type in ("below_ma", "above_ma"):
        reference = stop_loss.get("reference_indicator")
        if reference is None:
            raise ValueError(f"{stop_type} stop_loss requires reference_indicator")
        return resolve_operand(reference, df)
    if stop_type in ("below_vwap", "above_vwap"):
        return vwap_series(df)
    if stop_type == "fixed_points":
        return None  # handled by src/engine/backtest.py via vectorbt's sl_stop
    raise ValueError(f"unsupported stop_loss type={stop_type!r}")


def compute_exit_signal(canonical_logic: dict, df: pd.DataFrame, sr_target_price: float | None = None) -> pd.Series:
    """Level-based exits only (prior/day high-low, SuperTrend line, S/R) —
    close crossing a target level (take-profit) or a stop level (stop-loss).
    fixed_points targets/stops are NOT included here; src/engine/backtest.py
    layers those on separately via vectorbt's entry-relative sl_stop/tp_stop,
    since they need the actual per-trade entry price this module doesn't
    track (see FIXED_POINTS_TARGET_TYPE).
    """
    exit_config = canonical_logic["exit"]
    close = df["close"]

    target_hit = pd.Series(False, index=df.index)
    for target in exit_config["targets"]:
        level = _resolve_target_level(target, df, sr_target_price)
        if level is not None:
            target_hit = target_hit | (close >= level)

    stop_level = _resolve_stop_level(exit_config["stop_loss"], df)
    stop_hit = (close <= stop_level) if stop_level is not None else pd.Series(False, index=df.index)

    return (target_hit | stop_hit).fillna(False)


def has_fixed_points_target(canonical_logic: dict) -> float | None:
    for target in canonical_logic["exit"]["targets"]:
        if target.get("type") == FIXED_POINTS_TARGET_TYPE:
            return target.get("value")
    return None


def has_fixed_points_stop(canonical_logic: dict) -> float | None:
    stop_loss = canonical_logic["exit"]["stop_loss"]
    return stop_loss.get("value") if stop_loss.get("type") == FIXED_POINTS_TARGET_TYPE else None
