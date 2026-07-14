"""Risk guardrail evaluation (F8.1) — pure functions, no I/O. Deterministic
computations over structured inputs (docs/CLAUDE.md section 3), same
convention as every other scoring/classification function in src/engine/.

Threshold resolution (DB row vs. defaults) lives in
src/db/risk_settings.py; this module only evaluates already-resolved
settings against a candidate recommendation.
"""

from datetime import date

# No formula for expiry-day conviction dampening exists anywhere in the
# original spec — a new documented heuristic, same posture as
# conviction_score (Phase 4) and the negation-heuristic table (Phase 3):
# a fixed 30% reduction, not zero, so an expiry-day setup that's otherwise
# strong isn't erased outright — that's what suppression (a hard "don't
# fire") is for, dampening is a softer signal.
EXPIRY_DAY_CONVICTION_DAMPENING = 0.7


def is_expiry_day(today: date, expiry_weekday: int) -> bool:
    """expiry_weekday: Python's date.weekday() convention (Monday=0 ...
    Sunday=6) — founder-editable (src/db/models.py's RiskSettings), not a
    hardcoded assumption about NSE's current weekly-expiry weekday.
    """
    return today.weekday() == expiry_weekday


def should_suppress_tactical(category: str, vix_regime: str, suppress_tactical_on_extreme: bool) -> bool:
    return category == "tactical" and vix_regime == "extreme" and suppress_tactical_on_extreme


def apply_expiry_dampening(conviction_score: float, is_expiry: bool, expiry_day_dampening_enabled: bool) -> float:
    if is_expiry and expiry_day_dampening_enabled:
        return round(conviction_score * EXPIRY_DAY_CONVICTION_DAMPENING, 2)
    return conviction_score
