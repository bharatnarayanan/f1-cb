"""Confidence / risk / conviction scoring engine (F4.3).

Confidence formula is docs/buildspec.json's documented weighted sum:
0.25*macro_SR + 0.25*heavyweight_alignment + 0.20*strike_candle_pattern +
0.15*OI_accumulation + 0.15*RSI_alignment. Per the scope decision for this
pass (docs/assumptions.md), strike_candle_pattern and OI_accumulation stay
None — nothing in this codebase fetches option-chain/strike data yet — and
their weight is proportionally redistributed across the factors that ARE
known, not silently dropped, so confidence isn't permanently capped below
its available evidence. Every score here is a deterministic computation
over structured inputs (docs/CLAUDE.md section 3) — the LLM never touches
these numbers, only narrates the finished tree (see src/llm/narration.py).

conviction_score has no formula anywhere in the spec — it's a new,
documented assumption here: confidence dampened by risk, capped at a 50%
maximum reduction so risk alone can never zero out a genuinely strong
signal (that's what risk_score is already for, shown alongside it — see
docs/CLAUDE.md section 6: "never present confidence alone as if risk were
zero," the same principle applied in the other direction).
"""

from dataclasses import dataclass
from typing import Any

CONFIDENCE_WEIGHTS: dict[str, float] = {
    "macro_sr_alignment": 0.25,
    "heavyweight_pattern_alignment": 0.25,
    "strike_candle_pattern": 0.20,
    "oi_accumulation": 0.15,
    "rsi_alignment": 0.15,
}

# Base risk contributed purely by the current VIX regime (0-100 scale) —
# docs/assumptions.md #7's thresholds, translated into a risk score rather
# than a suppression flag (suppression itself is a later, route-level
# decision built on top of this number).
VIX_REGIME_RISK: dict[str, float] = {
    "normal": 20.0,
    "elevated": 45.0,
    "high": 70.0,
    "extreme": 90.0,
}
_EXPIRY_DAY_RISK_ADD = 15.0
_LOW_LIQUIDITY_RISK_ADD = 15.0

# How much a maxed-out risk score can dampen conviction relative to
# confidence — never more than this fraction, so risk alone can't zero out
# conviction (see module docstring).
_MAX_CONVICTION_RISK_DAMPENING = 0.5

# Distance (as a fraction of price) used to normalize a lone-sided S/R
# distance when only a support OR a resistance level is known, not both —
# a documented starting scale, not derived from real trade outcomes yet.
_SR_ROOM_REFERENCE_PCT = 0.005


@dataclass(frozen=True)
class SrContextLevel:
    level_price: float
    level_type: str  # "support" | "resistance"


def compute_macro_sr_alignment(current_price: float, direction: str, sr_levels: list[SrContextLevel]) -> float:
    """0-1: how much room the price has to move in `direction` before
    hitting an adverse level, relative to how close it already is to a
    supportive one. 0.5 (neutral) when there's no relevant S/R context at
    all — absence of data is not evidence against the setup.
    """
    if direction not in ("bullish", "bearish"):
        raise ValueError(f"unknown direction={direction!r}")

    if direction == "bullish":
        supportive = [lvl.level_price for lvl in sr_levels if lvl.level_type == "support" and lvl.level_price <= current_price]
        adverse = [lvl.level_price for lvl in sr_levels if lvl.level_type == "resistance" and lvl.level_price >= current_price]
    else:
        supportive = [lvl.level_price for lvl in sr_levels if lvl.level_type == "resistance" and lvl.level_price >= current_price]
        adverse = [lvl.level_price for lvl in sr_levels if lvl.level_type == "support" and lvl.level_price <= current_price]

    supportive_distance = min((abs(current_price - p) for p in supportive), default=None)
    adverse_distance = min((abs(p - current_price) for p in adverse), default=None)

    if supportive_distance is None and adverse_distance is None:
        return 0.5
    if adverse_distance is None:
        return 1.0
    if supportive_distance is None:
        reference = current_price * _SR_ROOM_REFERENCE_PCT
        return round(min(1.0, adverse_distance / reference), 3) if reference > 0 else 0.5

    total = supportive_distance + adverse_distance
    return round(adverse_distance / total, 3) if total > 0 else 0.5


def compute_rsi_alignment(rsi: float | None, direction: str) -> float:
    """0-1: how strongly RSI momentum agrees with `direction`. 0.5 when RSI
    isn't available (not enough bars) — same "absence isn't evidence
    against" principle as compute_macro_sr_alignment.
    """
    if direction not in ("bullish", "bearish"):
        raise ValueError(f"unknown direction={direction!r}")
    if rsi is None:
        return 0.5

    if direction == "bullish":
        return round(max(0.0, min(1.0, (rsi - 50) / 50)), 3)
    return round(max(0.0, min(1.0, (50 - rsi) / 50)), 3)


def compute_confidence(
    macro_sr_alignment: float,
    heavyweight_pattern_alignment: float,
    rsi_alignment: float,
    strike_candle_pattern: float | None = None,
    oi_accumulation: float | None = None,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """weights: overrides CONFIDENCE_WEIGHTS's hardcoded defaults — passed
    by the I/O layer (src/recommendation_pipeline.py) after resolving the
    founder's current factor_weights DB row (src/db/factor_weights.py).
    Stays a plain dict-in, no DB access here — this module stays pure/
    deterministic (docs/CLAUDE.md section 3) regardless of where the
    weights came from.
    """
    weights = weights or CONFIDENCE_WEIGHTS
    factors = {
        "macro_sr_alignment": macro_sr_alignment,
        "heavyweight_pattern_alignment": heavyweight_pattern_alignment,
        "rsi_alignment": rsi_alignment,
        "strike_candle_pattern": strike_candle_pattern,
        "oi_accumulation": oi_accumulation,
    }
    available = {name: value for name, value in factors.items() if value is not None}
    unavailable_factors = [name for name, value in factors.items() if value is None]
    if not available:
        raise ValueError("compute_confidence needs at least one known factor")

    weight_sum = sum(weights[name] for name in available)
    breakdown = {}
    for name, value in available.items():
        renormalized_weight = weights[name] / weight_sum
        breakdown[name] = {
            "value": value,
            "base_weight": weights[name],
            "renormalized_weight": round(renormalized_weight, 4),
            "contribution": round(value * renormalized_weight, 4),
        }

    score = round(sum(item["contribution"] for item in breakdown.values()) * 100, 2)
    return {"score": score, "factors": breakdown, "unavailable_factors": unavailable_factors}


def compute_risk(vix_regime: str, is_expiry_day: bool = False, is_low_liquidity: bool = False) -> dict[str, Any]:
    base = VIX_REGIME_RISK.get(vix_regime)
    if base is None:
        raise ValueError(f"unknown vix_regime={vix_regime!r}")

    score = base
    reasons = [f"VIX regime '{vix_regime}' base risk: {base}"]
    if is_expiry_day:
        score = min(100.0, score + _EXPIRY_DAY_RISK_ADD)
        reasons.append(f"expiry-day dampening: +{_EXPIRY_DAY_RISK_ADD}")
    if is_low_liquidity:
        score = min(100.0, score + _LOW_LIQUIDITY_RISK_ADD)
        reasons.append(f"low-liquidity flag: +{_LOW_LIQUIDITY_RISK_ADD}")

    return {
        "score": round(score, 2),
        "reasons": reasons,
        "vix_regime": vix_regime,
        "is_expiry_day": is_expiry_day,
        "is_low_liquidity": is_low_liquidity,
    }


def compute_conviction(confidence_score: float, risk_score: float) -> float:
    dampening = 1 - _MAX_CONVICTION_RISK_DAMPENING * (risk_score / 100)
    return round(confidence_score * dampening, 2)
