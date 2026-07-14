"""Resolves the founder's risk_settings DB row (Phase 7 Pass 2b, extended
Phase 8 for guardrail enforcement).

Prefers the founder's `risk_settings` DB row (editable via
src/routes/settings.py) over src/config.py's env-var defaults — the whole
point of the risk settings screen is that it actually controls behavior,
not just displays a number nobody reads. Falls back to defaults only if
the row is somehow missing (it's seeded by migration 0006, so this is a
defensive fallback, not the expected path).
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import Settings
from src.db.founder import get_founder
from src.db.models import RiskSettings


def get_vix_thresholds(db: Session, settings: Settings) -> tuple[float, float, float]:
    founder = get_founder(db)
    row = db.execute(select(RiskSettings).where(RiskSettings.user_id == founder.id)).scalar_one_or_none()
    if row is not None:
        return float(row.vix_normal_max), float(row.vix_elevated_max), float(row.vix_high_max)
    return settings.vix_normal_max, settings.vix_elevated_max, settings.vix_high_max


@dataclass(frozen=True)
class GuardrailSettings:
    suppress_tactical_on_extreme: bool
    expiry_day_dampening: bool
    expiry_weekday: int
    max_daily_recommendations: int


# Same values as the risk_settings columns' own DB defaults (src/db/models.py) —
# used only if the founder's row is somehow missing (migration 0006 seeds it).
_DEFAULT_GUARDRAILS = GuardrailSettings(
    suppress_tactical_on_extreme=True,
    expiry_day_dampening=True,
    expiry_weekday=1,  # Tuesday
    max_daily_recommendations=20,
)


def get_guardrail_settings(db: Session) -> GuardrailSettings:
    founder = get_founder(db)
    row = db.execute(select(RiskSettings).where(RiskSettings.user_id == founder.id)).scalar_one_or_none()
    if row is None:
        return _DEFAULT_GUARDRAILS
    return GuardrailSettings(
        suppress_tactical_on_extreme=row.suppress_tactical_on_extreme,
        expiry_day_dampening=row.expiry_day_dampening,
        expiry_weekday=row.expiry_weekday,
        max_daily_recommendations=row.max_daily_recommendations,
    )
