"""India VIX regime classification — pure function, no I/O.

Explicit thresholds, not a Settings object: callers resolve the actual
threshold values first (src/db/risk_settings.py — the founder's DB
risk_settings row in preference to env-var defaults, Phase 7 Pass 2b) so
this function stays a pure classification with no config or DB coupling.
"""

VixRegime = str  # "normal" | "elevated" | "high" | "extreme"


def compute_vix_regime(value: float, normal_max: float, elevated_max: float, high_max: float) -> VixRegime:
    if value < normal_max:
        return "normal"
    if value < elevated_max:
        return "elevated"
    if value < high_max:
        return "high"
    return "extreme"
