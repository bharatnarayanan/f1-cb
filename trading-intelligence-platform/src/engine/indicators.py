"""Thin TA-Lib indicator wrappers shared across the scoring engine."""

from typing import Any

import numpy as np
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
