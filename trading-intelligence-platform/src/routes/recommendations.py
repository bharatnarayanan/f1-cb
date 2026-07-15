"""On-demand recommendation route (F4.1-F4.4).

Thin wrapper around src/recommendation_pipeline.py's generate_recommendation
— the actual pattern -> negation -> correlation -> scoring -> narration ->
persistence -> alert-dispatch pipeline is shared with the scheduled
`worker` service (src/worker/main.py) so the two never drift (Phase 8,
worker service pass). This route stays as the on-demand, manually-triggered
entry point; repeated calls with overlapping windows can still persist
duplicate rows the same way they always could — the worker is what dedupes
by newest-scanned-bar (src/worker/main.py).

Only Tactical (a detected candlestick pattern on a supported timeframe) and
Impulse (an outlier-sized move on the 5m feed) categories are reachable
here — see src/engine/recommendations.py for why Strategic/BTST aren't yet.

No route here places, modifies, or cancels a broker order — see
docs/CLAUDE.md section 2. entry/exit/strike stay unset (see
src/engine/recommendations.py's docstring): action is a directional CE/PE
proxy only, never a specific instrument to trade.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user
from src.config import Settings, get_settings
from src.db.models import Recommendation, User
from src.db.session import get_db
from src.market_data.base import MarketDataClient
from src.market_data.exceptions import MarketDataInvalidRequest
from src.market_data.factory import get_market_data_client
from src.recommendation_pipeline import generate_recommendation

router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendations"])


@router.post("/{symbol}")
def create_recommendation(
    symbol: str,
    exchange: str = "NSE",
    timeframe: str = "15m",
    market: MarketDataClient = Depends(get_market_data_client),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: User = Depends(get_current_user),
) -> dict:
    return generate_recommendation(
        symbol=symbol, exchange=exchange, timeframe=timeframe, market=market, db=db, settings=settings
    )


def _serialize_recommendation_summary(row: Recommendation) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "symbol": row.symbol,
        "category": row.category,
        "action": row.action,
        "forecast_horizon": row.forecast_horizon,
        "confidence_score": float(row.confidence_score),
        "risk_score": float(row.risk_score),
        "conviction_score": float(row.conviction_score),
        "vix_regime_at_creation": row.vix_regime_at_creation,
        "status": row.status,
        "created_at": row.created_at.isoformat(),
    }


@router.get("")
def list_recommendations(
    category: str | None = None,
    status: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    query = select(Recommendation).order_by(Recommendation.created_at.desc()).limit(limit)
    if category is not None:
        query = query.where(Recommendation.category == category)
    if status is not None:
        query = query.where(Recommendation.status == status)

    rows = db.execute(query).scalars().all()
    return {"recommendations": [_serialize_recommendation_summary(row) for row in rows]}


@router.get("/{recommendation_id}")
def get_recommendation(
    recommendation_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> dict[str, Any]:
    try:
        parsed_id = uuid.UUID(recommendation_id)
    except ValueError:
        raise MarketDataInvalidRequest(f"{recommendation_id!r} is not a valid recommendation id.")

    row = db.get(Recommendation, parsed_id)
    if row is None:
        raise MarketDataInvalidRequest(f"No recommendation found with id={recommendation_id!r}.")

    summary = _serialize_recommendation_summary(row)
    summary["rationale"] = row.rationale
    return summary
