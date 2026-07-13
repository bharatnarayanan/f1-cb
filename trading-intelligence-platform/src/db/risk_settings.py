"""Resolves the founder's VIX-regime thresholds (Phase 7 Pass 2b).

Prefers the founder's `risk_settings` DB row (editable via
src/routes/settings.py) over src/config.py's env-var defaults — the whole
point of the risk settings screen is that it actually controls VIX regime
classification, not just displays a number nobody reads. Falls back to env
defaults only if the row is somehow missing (it's seeded by migration
0006, so this is a defensive fallback, not the expected path).
"""

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
