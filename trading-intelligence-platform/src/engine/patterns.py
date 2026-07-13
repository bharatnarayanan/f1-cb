"""Multi-timeframe candlestick pattern detection (F3.1).

Wraps TA-Lib's CDL* pattern-recognition functions — docs/CLAUDE.md section 4
locks TA-Lib as the pattern-detection library, do not reimplement this math
by hand. "Pin bar" has no native TA-Lib function, so it's the one pattern
detected with a hand-rolled geometric rule (small body near one end of the
bar's range, a long opposite wick) — a standard price-action definition,
not a TA-Lib gap.

Every pattern_type here must match the CHECK-free but documented set in
database/schema.sql's patterns_detected.pattern_type comment: engulfing |
three_inside | three_outside | harami | doji | pin_bar.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

import numpy as np
import talib

# TA-Lib CDL* functions return, per bar, 100 (bullish), -100 (bearish), or 0
# (no pattern) — signal lands on the LAST bar of a multi-candle pattern.
_TALIB_PATTERN_FUNCTIONS: dict[str, Callable[..., np.ndarray]] = {
    "engulfing": talib.CDLENGULFING,
    "three_inside": talib.CDL3INSIDE,
    "three_outside": talib.CDL3OUTSIDE,
    "harami": talib.CDLHARAMI,
    "doji": talib.CDLDOJI,
}

# Conservative floor so we never score a pattern before TA-Lib's own
# lookback is satisfied — docs/CLAUDE.md section 6: "don't score a pattern
# until enough bars exist." Most CDL* functions need only 1-3 prior bars,
# but doji-family functions internally average body size over a 10-bar
# window (TA-Lib's default CandleAverage period) before they'll ever flag a
# match — empirically confirmed to need 11 bars minimum. 15 keeps margin.
_MIN_BARS_FOR_DETECTION = 15

# Pin bar: body must be small relative to the full bar range, and the
# dominant wick must be at least this many times the body. Tightened from
# an initial 0.35/2.0x after a real sample-mode scan showed the looser
# thresholds flagging pin bars on ~15% of ordinary small-bodied candles —
# too noisy to be a useful signal. A starting heuristic either way; real
# calibration is a trade-journal feedback-loop job (later phase), not
# something to hand-tune further here without outcome data.
_PIN_BAR_BODY_TO_RANGE_MAX = 0.3
_PIN_BAR_WICK_TO_BODY_RATIO = 2.5


@dataclass(frozen=True)
class DetectedPattern:
    pattern_type: str
    direction: str  # "bullish" | "bearish"
    bar_ts: datetime


def detect_patterns(candles: list[dict[str, Any]]) -> list[DetectedPattern]:
    """candles: ascending-time OHLCV dicts with an "open"/"high"/"low"/"close"
    and a "date" (or "ts") timestamp key — the shape MarketDataClient
    implementations already return.
    """
    if len(candles) < _MIN_BARS_FOR_DETECTION:
        return []

    opens = np.array([c["open"] for c in candles], dtype=float)
    highs = np.array([c["high"] for c in candles], dtype=float)
    lows = np.array([c["low"] for c in candles], dtype=float)
    closes = np.array([c["close"] for c in candles], dtype=float)
    timestamps = [c.get("date") or c["ts"] for c in candles]

    detected: list[DetectedPattern] = []
    for pattern_type, fn in _TALIB_PATTERN_FUNCTIONS.items():
        result = fn(opens, highs, lows, closes)
        for i, value in enumerate(result):
            if value != 0:
                detected.append(
                    DetectedPattern(
                        pattern_type=pattern_type,
                        direction="bullish" if value > 0 else "bearish",
                        bar_ts=timestamps[i],
                    )
                )

    detected.extend(_detect_pin_bars(opens, highs, lows, closes, timestamps))
    return detected


def _detect_pin_bars(
    opens: np.ndarray, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, timestamps: list[datetime]
) -> list[DetectedPattern]:
    detected: list[DetectedPattern] = []
    for i in range(len(opens)):
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        full_range = h - l
        body = abs(c - o)
        if full_range <= 0 or body == 0 or body / full_range > _PIN_BAR_BODY_TO_RANGE_MAX:
            continue

        upper_wick = h - max(o, c)
        lower_wick = min(o, c) - l
        if lower_wick >= _PIN_BAR_WICK_TO_BODY_RATIO * body and lower_wick > upper_wick:
            detected.append(DetectedPattern("pin_bar", "bullish", timestamps[i]))
        elif upper_wick >= _PIN_BAR_WICK_TO_BODY_RATIO * body and upper_wick > lower_wick:
            detected.append(DetectedPattern("pin_bar", "bearish", timestamps[i]))
    return detected
