"""Recommendation generation (F4.4) — assembles a scored, ready-to-persist
recommendation from the Phase 3 engine's outputs plus Phase 4's scoring.

Only Tactical and Impulse categories are built in this pass — Strategic
(2-5 day outlook) needs daily candles and BTST (expiry-adjacent) needs an
options-expiry calendar, and neither exists yet (docs/assumptions.md).
Asking for any other timeframe raises loudly rather than silently
mislabeling a recommendation's category.

action is a directional proxy (BUY_CE for bullish, BUY_PE for bearish) —
strike/entry/exit/option_type stay unset. There's no strike-selection logic
or option-chain pricing built yet (same scope decision as
src/engine/scoring.py's OI_accumulation/strike_candle_pattern gap), so
recommending a specific strike or price here would be fabricating
precision this system doesn't actually have — docs/CLAUDE.md section 6.
"""

from dataclasses import asdict, dataclass
from typing import Any

from src.engine.correlation import ConstituentMomentum
from src.engine.negation import NegationEstimate
from src.engine.scoring import (
    SrContextLevel,
    compute_confidence,
    compute_conviction,
    compute_macro_sr_alignment,
    compute_risk,
    compute_rsi_alignment,
)

_TACTICAL_TIMEFRAMES = {"15m", "30m", "1h", "2h"}


@dataclass(frozen=True)
class RecommendationDraft:
    category: str
    action: str
    forecast_horizon: str
    confidence_score: float
    risk_score: float
    conviction_score: float
    rationale: dict[str, Any]


def build_recommendation(
    *,
    pattern_type: str,
    direction: str,
    timeframe: str,
    bar_ts,
    current_price: float,
    sr_levels: list[SrContextLevel],
    correlation_score: float,
    correlation_breakdown: list[ConstituentMomentum],
    rsi: float | None,
    vix_regime: str,
    is_impulse: bool,
    negation_estimate: NegationEstimate,
) -> RecommendationDraft:
    if direction not in ("bullish", "bearish"):
        raise ValueError(f"unknown direction={direction!r}")

    if is_impulse:
        category, forecast_horizon = "impulse", timeframe
    elif timeframe in _TACTICAL_TIMEFRAMES:
        category, forecast_horizon = "tactical", timeframe
    else:
        raise ValueError(
            f"no recommendation category available for timeframe={timeframe!r} outside an impulse move — "
            "Strategic (2-5d) needs daily candles and BTST needs an expiry calendar, neither built yet."
        )

    action = "BUY_CE" if direction == "bullish" else "BUY_PE"

    macro_sr_alignment = compute_macro_sr_alignment(current_price, direction, sr_levels)
    rsi_alignment = compute_rsi_alignment(rsi, direction)
    confidence = compute_confidence(
        macro_sr_alignment=macro_sr_alignment,
        heavyweight_pattern_alignment=correlation_score,
        rsi_alignment=rsi_alignment,
    )
    risk = compute_risk(vix_regime)
    conviction_score = compute_conviction(confidence["score"], risk["score"])

    rationale = {
        "pattern": {"type": pattern_type, "direction": direction, "timeframe": timeframe, "bar_ts": str(bar_ts)},
        "negation": {
            "model_version": negation_estimate.model_version,
            "predicted_candles": negation_estimate.predicted_candles,
            "predicted_window_end": str(negation_estimate.predicted_window_end),
        },
        "correlation": {
            "score": correlation_score,
            "constituents": [asdict(c) for c in correlation_breakdown],
        },
        "rsi": rsi,
        "confidence": confidence,
        "risk": risk,
        "conviction_score": conviction_score,
        # Filled in by src/llm/narration.py — the LLM narrates this
        # already-computed tree, it never produces the numbers in it.
        "narrative": None,
    }

    return RecommendationDraft(
        category=category,
        action=action,
        forecast_horizon=forecast_horizon,
        confidence_score=confidence["score"],
        risk_score=risk["score"],
        conviction_score=conviction_score,
        rationale=rationale,
    )
