"""India VIX regime classification — pure function, no I/O.

Thresholds locked in docs/assumptions.md #7: Normal < 15, Elevated 15-20,
High 20-30, Extreme > 30 (configurable per docs/config.py settings /
future per-user risk_settings row). This is the same formula the
risk-guardrail scoring engine (later phase) will reuse — kept here rather
than duplicated because it only needs the raw VIX value and the three
threshold settings, no other scoring-engine state.
"""

from src.config import Settings

VixRegime = str  # "normal" | "elevated" | "high" | "extreme"


def compute_vix_regime(value: float, settings: Settings) -> VixRegime:
    if value < settings.vix_normal_max:
        return "normal"
    if value < settings.vix_elevated_max:
        return "elevated"
    if value < settings.vix_high_max:
        return "high"
    return "extreme"
