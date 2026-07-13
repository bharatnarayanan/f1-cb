"""Trade journal routes (F6.3) — logging only.

Manual outcome logging is the input the future Bayesian pattern/negation
weight-update job will consume — that job itself needs the scheduled
`worker` service, which no phase has built yet (docs/assumptions.md).
Logging ships now; the learning loop is explicitly deferred, not silently
dropped.
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.db.models import TradeJournalEntry, User
from src.db.session import get_db
from src.market_data.exceptions import MarketDataInvalidRequest

router = APIRouter(prefix="/api/v1/journal", tags=["journal"])

FOUNDER_EMAIL = "founder@local"  # seeded by alembic/versions/0004_seed_founder_strategy.py

_VALID_OUTCOMES = {"win", "loss", "breakeven", "not_taken"}


class JournalEntryRequest(BaseModel):
    recommendation_id: str | None = None
    outcome: str
    realized_pnl_pct: float | None = None
    observation: str | None = None


def _get_founder(db: Session) -> User:
    founder = db.execute(select(User).where(User.email == FOUNDER_EMAIL)).scalar_one_or_none()
    if founder is None:
        raise RuntimeError(f"No founder user found (email={FOUNDER_EMAIL!r}) — check migration 0004 ran.")
    return founder


@router.post("")
def log_outcome(body: JournalEntryRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    if body.outcome not in _VALID_OUTCOMES:
        raise MarketDataInvalidRequest(f"unsupported outcome={body.outcome!r} — use one of {sorted(_VALID_OUTCOMES)}.")

    founder = _get_founder(db)
    entry = TradeJournalEntry(
        recommendation_id=body.recommendation_id,
        user_id=founder.id,
        outcome=body.outcome,
        realized_pnl_pct=body.realized_pnl_pct,
        observation=body.observation,
    )

    try:
        db.add(entry)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    return {
        "id": str(entry.id),
        "recommendation_id": body.recommendation_id,
        "outcome": entry.outcome,
        "realized_pnl_pct": entry.realized_pnl_pct,
        "logged_at": entry.logged_at.isoformat() if entry.logged_at else datetime.now(timezone.utc).isoformat(),
    }


@router.get("")
def list_entries(db: Session = Depends(get_db)) -> dict[str, Any]:
    entries = db.execute(select(TradeJournalEntry).order_by(TradeJournalEntry.logged_at.desc())).scalars().all()
    return {
        "entries": [
            {
                "id": str(e.id),
                "recommendation_id": str(e.recommendation_id) if e.recommendation_id else None,
                "outcome": e.outcome,
                "realized_pnl_pct": e.realized_pnl_pct,
                "observation": e.observation,
            }
            for e in entries
        ]
    }
