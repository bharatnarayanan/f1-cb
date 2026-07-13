"""Heavyweight/sector correlation engine (F4.1).

Scores whether the watchlist (top-15-by-weight NIFTY constituents + 5
sector indices, docs/assumptions.md #6) confirms the index-level pattern's
direction — a bullish NIFTY pattern means more if heavyweight constituents
are ALSO trending bullish, not contradicting it. Deterministic momentum-sign
agreement, no ML (docs/CLAUDE.md section 3).
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ConstituentMomentum:
    symbol: str
    direction: str  # "bullish" | "bearish" | "flat"


def momentum_direction(candles: list[dict[str, Any]], lookback: int = 5) -> str:
    """Sign of the close-to-close return over the last `lookback` candles.

    "flat" if there's not enough data or the move is exactly zero — never
    silently defaults to a direction when we don't actually know one.
    """
    if len(candles) < lookback + 1:
        return "flat"

    start_close = candles[-(lookback + 1)]["close"]
    end_close = candles[-1]["close"]
    if end_close > start_close:
        return "bullish"
    if end_close < start_close:
        return "bearish"
    return "flat"


def score_correlation(
    index_direction: str, constituent_candles: dict[str, list[dict[str, Any]]], lookback: int = 5
) -> tuple[float, list[ConstituentMomentum]]:
    """Fraction (0-1) of the watchlist whose momentum direction agrees with
    index_direction. "flat" constituents count as neither agreeing nor
    disagreeing — excluded from the denominator, not counted against the
    score, since "no clear direction" isn't the same as "disagreement."

    Returns (score, per-constituent breakdown) so callers can show their
    work in a reasoning tree rather than a bare number.
    """
    breakdown = [
        ConstituentMomentum(symbol=symbol, direction=momentum_direction(candles, lookback))
        for symbol, candles in constituent_candles.items()
    ]

    decisive = [c for c in breakdown if c.direction != "flat"]
    if not decisive:
        return 0.0, breakdown

    agreeing = sum(1 for c in decisive if c.direction == index_direction)
    return round(agreeing / len(decisive), 3), breakdown
