"""Thin TA-Lib indicator wrappers shared across the scoring engine and the
Phase 5 strategy interpreter (src/engine/strategy_interpreter.py).

compute_rsi (Phase 4) returns a single latest value for confidence scoring.
The *_series functions (Phase 5) return a full pandas Series aligned to the
input candles, because the strategy interpreter needs to evaluate a
condition at every bar, not just the most recent one.
"""

from typing import Any

import numpy as np
import pandas as pd
import talib

_DEFAULT_RSI_PERIOD = 14


def compute_rsi(candles: list[dict[str, Any]], period: int = _DEFAULT_RSI_PERIOD) -> float | None:
    """Latest RSI value, or None if there aren't enough bars for TA-Lib's
    own lookback (period + 1) — never fabricate a value on insufficient data.
    """
    if len(candles) < period + 1:
        return None

    closes = np.array([c["close"] for c in candles], dtype=float)
    result = talib.RSI(closes, timeperiod=period)
    latest = result[-1]
    return None if np.isnan(latest) else round(float(latest), 2)


def sma_series(df: pd.DataFrame, period: int) -> pd.Series:
    return pd.Series(talib.SMA(df["close"].to_numpy(dtype=float), timeperiod=period), index=df.index)


def ema_series(df: pd.DataFrame, period: int) -> pd.Series:
    return pd.Series(talib.EMA(df["close"].to_numpy(dtype=float), timeperiod=period), index=df.index)


def rsi_series(df: pd.DataFrame, period: int) -> pd.Series:
    return pd.Series(talib.RSI(df["close"].to_numpy(dtype=float), timeperiod=period), index=df.index)


def macd_series(df: pd.DataFrame, period: int, params: dict | None = None) -> pd.Series:
    """Returns the MACD line itself (not the signal line or histogram) —
    docs/strategy_schema.json's operand shape only guarantees a single
    `period` int plus a free-form `params` object, not MACD's usual
    fast/slow/signal triple, so `period` is treated as the fast period and
    slow/signal come from `params` (defaulting to TA-Lib's own 26/9).
    """
    params = params or {}
    macd, _signal, _hist = talib.MACD(
        df["close"].to_numpy(dtype=float),
        fastperiod=period,
        slowperiod=params.get("slowperiod", 26),
        signalperiod=params.get("signalperiod", 9),
    )
    return pd.Series(macd, index=df.index)


def vwap_series(df: pd.DataFrame) -> pd.Series:
    """Continuous cumulative VWAP over the whole fetched window — NOT reset
    at session/day boundaries (this codebase doesn't track session
    boundaries yet). A documented simplification, not a session VWAP —
    docs/CLAUDE.md section 6: backtests must document their assumptions.
    """
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    cum_tp_vol = (typical_price * df["volume"]).cumsum()
    cum_vol = df["volume"].cumsum().replace(0, np.nan)
    return cum_tp_vol / cum_vol


def supertrend_series(df: pd.DataFrame, period: int = 7, multiplier: float = 3.0) -> pd.Series:
    """Standard SuperTrend: ATR-based bands with the usual carry-forward and
    flip rules. Iterative by construction (each bar's band/direction
    depends on the previous bar's) — not vectorizable, fine at backtest-
    window scale (hundreds to low thousands of bars).
    """
    atr = talib.ATR(
        df["high"].to_numpy(dtype=float), df["low"].to_numpy(dtype=float), df["close"].to_numpy(dtype=float),
        timeperiod=period,
    )
    hl2 = (df["high"] + df["low"]) / 2
    upperband = hl2 + multiplier * atr
    lowerband = hl2 - multiplier * atr
    closes = df["close"].to_numpy(dtype=float)

    final_upper = np.full(len(df), np.nan)
    final_lower = np.full(len(df), np.nan)
    supertrend = np.full(len(df), np.nan)

    for i in range(len(df)):
        if i == 0 or np.isnan(atr[i - 1]):
            final_upper[i] = upperband.iloc[i]
            final_lower[i] = lowerband.iloc[i]
            supertrend[i] = upperband.iloc[i]
            continue

        final_upper[i] = (
            upperband.iloc[i]
            if (upperband.iloc[i] < final_upper[i - 1] or closes[i - 1] > final_upper[i - 1])
            else final_upper[i - 1]
        )
        final_lower[i] = (
            lowerband.iloc[i]
            if (lowerband.iloc[i] > final_lower[i - 1] or closes[i - 1] < final_lower[i - 1])
            else final_lower[i - 1]
        )

        if supertrend[i - 1] == final_upper[i - 1]:
            supertrend[i] = final_upper[i] if closes[i] <= final_upper[i] else final_lower[i]
        else:
            supertrend[i] = final_lower[i] if closes[i] >= final_lower[i] else final_upper[i]

    return pd.Series(supertrend, index=df.index)
