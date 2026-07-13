"""Candle-negation heuristic model (F3.2).

MVP heuristic per docs/CLAUDE.md section 4 and docs/assumptions.md #3: a
statistical/heuristic estimate (avg candles-to-negate per pattern type,
scaled by VIX regime and timeframe), NOT the v1.1 LSTM upgrade — there is
no trade-journal history yet to train a model on. This is a deterministic
computation over structured inputs (docs/CLAUDE.md section 3: the LLM never
decides a numeric score) — every output is reproducible from its inputs.

The base candles-to-negate table below is a documented starting default
(no historical backtest data exists yet to derive it from) — see
docs/assumptions.md. It's designed to be swapped for backtest-derived
values, or replaced by the negation_predictions.model_version-tagged LSTM
upgrade, without a schema migration.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

MODEL_VERSION = "heuristic-v1"

# Average bars (of the pattern's OWN timeframe) until a pattern is
# considered negated, in a "normal" VIX regime. A documented starting
# assumption, not derived from real trade data yet — see docs/assumptions.md.
_BASE_CANDLES_TO_NEGATE: dict[str, float] = {
    "engulfing": 3.0,
    "three_inside": 4.0,
    "three_outside": 4.0,
    "harami": 5.0,
    "doji": 2.5,
    "pin_bar": 3.5,
}

# Higher VIX regimes negate patterns faster (more volatile price action
# invalidates a setup sooner) — multiplier applied to the base estimate.
_VIX_REGIME_MULTIPLIER: dict[str, float] = {
    "normal": 1.0,
    "elevated": 0.85,
    "high": 0.65,
    "extreme": 0.45,
}

_TIMEFRAME_MINUTES: dict[str, int] = {
    "5m": 5,
    "10m": 10,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "2h": 120,
    "3h": 180,
}


@dataclass(frozen=True)
class NegationEstimate:
    predicted_candles: float
    predicted_window_start: datetime
    predicted_window_end: datetime
    model_version: str = MODEL_VERSION


def predict_negation(pattern_type: str, timeframe: str, vix_regime: str, bar_ts: datetime) -> NegationEstimate:
    base = _BASE_CANDLES_TO_NEGATE.get(pattern_type)
    if base is None:
        raise ValueError(f"no negation heuristic defined for pattern_type={pattern_type!r}")

    multiplier = _VIX_REGIME_MULTIPLIER.get(vix_regime)
    if multiplier is None:
        raise ValueError(f"unknown vix_regime={vix_regime!r}")

    tf_minutes = _TIMEFRAME_MINUTES.get(timeframe)
    if tf_minutes is None:
        raise ValueError(f"unknown timeframe={timeframe!r}")

    predicted_candles = round(base * multiplier, 2)
    window_minutes = predicted_candles * tf_minutes
    window_end = bar_ts + timedelta(minutes=window_minutes)

    return NegationEstimate(
        predicted_candles=predicted_candles,
        predicted_window_start=bar_ts,
        predicted_window_end=window_end,
    )
