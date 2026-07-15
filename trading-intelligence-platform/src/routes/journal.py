"""Trade journal routes (F6.3 logging; weight recompute added CLAUDE.md
item 9).

Manual outcome logging is the input the Bayesian confidence-factor
weight-update job (src/db/factor_weights.py) consumes — recompute is
founder-triggered here, not automatic, so a scoring change never happens
silently (see that module's docstring for the actual math).
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user
from src.db.factor_weights import get_confidence_weights, recompute_factor_weights
from src.db.founder import get_founder
from src.db.models import TradeJournalEntry, User
from src.db.session import get_db
from src.market_data.exceptions import MarketDataInvalidRequest

router = APIRouter(prefix="/api/v1/journal", tags=["journal"])

_VALID_OUTCOMES = {"win", "loss", "breakeven", "not_taken"}


class JournalEntryRequest(BaseModel):
    recommendation_id: str | None = None
    outcome: str
    realized_pnl_pct: float | None = None
    observation: str | None = None


@router.post("")
def log_outcome(
    body: JournalEntryRequest, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> dict[str, Any]:
    if body.outcome not in _VALID_OUTCOMES:
        raise MarketDataInvalidRequest(f"unsupported outcome={body.outcome!r} — use one of {sorted(_VALID_OUTCOMES)}.")

    founder = get_founder(db)
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
def list_entries(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict[str, Any]:
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


@router.get("/factor-weights")
def get_factor_weights(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict[str, Any]:
    return {"weights": get_confidence_weights(db)}


@router.post("/recompute-weights")
def recompute_weights(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict[str, Any]:
    try:
        summary = recompute_factor_weights(db)
    except SQLAlchemyError:
        db.rollback()
        raise
    return {"result": summary}
