"""Settings routes (Phase 7 Pass 2b): watchlist toggles, risk settings, and
a read-only alerts status.

Alerts config (Telegram/email) stays env-var-only, read once at container
startup — making it live-editable would need a real DB-backed config layer
src/alerts/* would have to read from, which is more architecture than a
single founder editing `.env` occasionally justifies right now (confirmed
before building). This route reports what's configured, it doesn't change
it.

execution_mode is validated against exactly "paper"/"live_manual" here,
on top of the DB enum constraint — docs/CLAUDE.md section 2 never allows a
third auto-execute mode, even behind a setting; a route that silently
accepted an unknown string and let Postgres be the only thing catching it
would be the wrong place to first notice that violation.
"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.config import Settings, get_settings
from src.db.founder import get_founder
from src.db.models import RiskSettings, SectorIndexRecord, WatchlistConstituent
from src.db.session import get_db
from src.market_data.exceptions import MarketDataInvalidRequest

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

_VALID_EXECUTION_MODES = {"paper", "live_manual"}


class ToggleActiveRequest(BaseModel):
    is_active: bool


class RiskSettingsUpdate(BaseModel):
    vix_normal_max: float | None = None
    vix_elevated_max: float | None = None
    vix_high_max: float | None = None
    suppress_tactical_on_extreme: bool | None = None
    expiry_day_dampening: bool | None = None
    expiry_weekday: int | None = None
    max_daily_recommendations: int | None = None
    execution_mode: str | None = None


def _serialize_risk_settings(row: RiskSettings) -> dict[str, Any]:
    return {
        "vix_normal_max": float(row.vix_normal_max),
        "vix_elevated_max": float(row.vix_elevated_max),
        "vix_high_max": float(row.vix_high_max),
        "suppress_tactical_on_extreme": row.suppress_tactical_on_extreme,
        "expiry_day_dampening": row.expiry_day_dampening,
        "expiry_weekday": row.expiry_weekday,
        "max_daily_recommendations": row.max_daily_recommendations,
        "execution_mode": row.execution_mode,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("/watchlist")
def get_watchlist(db: Session = Depends(get_db)) -> dict[str, Any]:
    constituents = db.execute(select(WatchlistConstituent).order_by(WatchlistConstituent.symbol)).scalars().all()
    sectors = db.execute(select(SectorIndexRecord).order_by(SectorIndexRecord.symbol)).scalars().all()
    return {
        "constituents": [
            {"symbol": c.symbol, "display_name": c.display_name, "sector": c.sector, "is_active": c.is_active}
            for c in constituents
        ],
        "sectors": [{"symbol": s.symbol, "display_name": s.display_name, "is_active": s.is_active} for s in sectors],
    }


@router.patch("/watchlist/constituents/{symbol}")
def toggle_constituent(symbol: str, body: ToggleActiveRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = db.execute(select(WatchlistConstituent).where(WatchlistConstituent.symbol == symbol)).scalar_one_or_none()
    if row is None:
        raise MarketDataInvalidRequest(f"No watchlist constituent found with symbol={symbol!r}.")
    row.is_active = body.is_active

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    return {"symbol": row.symbol, "is_active": row.is_active}


@router.patch("/watchlist/sectors/{symbol}")
def toggle_sector(symbol: str, body: ToggleActiveRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = db.execute(select(SectorIndexRecord).where(SectorIndexRecord.symbol == symbol)).scalar_one_or_none()
    if row is None:
        raise MarketDataInvalidRequest(f"No sector index found with symbol={symbol!r}.")
    row.is_active = body.is_active

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    return {"symbol": row.symbol, "is_active": row.is_active}


@router.get("/risk")
def get_risk_settings(db: Session = Depends(get_db)) -> dict[str, Any]:
    founder = get_founder(db)
    row = db.execute(select(RiskSettings).where(RiskSettings.user_id == founder.id)).scalar_one_or_none()
    if row is None:
        raise MarketDataInvalidRequest("No risk_settings row found for the founder — check migration 0006 ran.")
    return _serialize_risk_settings(row)


@router.put("/risk")
def update_risk_settings(body: RiskSettingsUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    if body.execution_mode is not None and body.execution_mode not in _VALID_EXECUTION_MODES:
        raise MarketDataInvalidRequest(
            f"execution_mode must be one of {sorted(_VALID_EXECUTION_MODES)} — no other mode is ever permitted."
        )
    if body.expiry_weekday is not None and not (0 <= body.expiry_weekday <= 6):
        raise MarketDataInvalidRequest(
            "expiry_weekday must be 0-6 (Python date.weekday() convention: Monday=0 ... Sunday=6)."
        )

    founder = get_founder(db)
    row = db.execute(select(RiskSettings).where(RiskSettings.user_id == founder.id)).scalar_one_or_none()
    if row is None:
        raise MarketDataInvalidRequest("No risk_settings row found for the founder — check migration 0006 ran.")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    return _serialize_risk_settings(row)


@router.get("/alerts")
def get_alerts_status(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    return {
        "telegram_configured": bool(settings.telegram_bot_token and settings.telegram_chat_id),
        "email_configured": bool(settings.smtp_host and settings.smtp_user and settings.smtp_password and settings.alert_email_to),
        "dashboard_configured": True,
        "note": (
            "Read-only — alert channels are configured via environment variables (.env), not editable here. "
            "See docs/assumptions.md #Phase 7 Pass 2b for why."
        ),
    }
