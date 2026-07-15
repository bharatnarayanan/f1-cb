"""Paper-trading routes (F6.1) — simulated fills ONLY. No real order, no
real money anywhere in this codebase. See docs/CLAUDE.md section 2.

Opening a trade locks in its exit rule (target/stop/expiry) at that moment
— see src/engine/paper_trading.py's module docstring for why closing never
recomputes it fresh.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user
from src.config import Settings, get_settings
from src.db.founder import get_founder
from src.db.models import PaperTrade, Recommendation, User
from src.db.session import get_db
from src.engine.paper_trading import compute_pnl_pct, evaluate_exit, resolve_exit_rule
from src.engine.scoring import SrContextLevel
from src.engine.support_resistance import calculate_sr_levels
from src.market_data.base import MarketDataClient
from src.market_data.exceptions import MarketDataInvalidRequest
from src.market_data.factory import get_market_data_client
from src.market_data.instruments import resolve_instrument_token

router = APIRouter(prefix="/api/v1/paper-trades", tags=["paper-trades"])

_ACTION_TO_DIRECTION = {"BUY_CE": "bullish", "BUY_PE": "bearish"}
_SR_LOOKBACK_HOURS = 8


class OpenPaperTradeRequest(BaseModel):
    recommendation_id: str


class ClosePaperTradeRequest(BaseModel):
    force: bool = False


def _get_recommendation_or_400(db: Session, recommendation_id: str) -> Recommendation:
    try:
        parsed_id = uuid.UUID(recommendation_id)
    except ValueError:
        raise MarketDataInvalidRequest(f"{recommendation_id!r} is not a valid recommendation id.")
    recommendation = db.get(Recommendation, parsed_id)
    if recommendation is None:
        raise MarketDataInvalidRequest(f"No recommendation found with id={recommendation_id!r}.")
    return recommendation


def _get_paper_trade_or_400(db: Session, paper_trade_id: str) -> PaperTrade:
    try:
        parsed_id = uuid.UUID(paper_trade_id)
    except ValueError:
        raise MarketDataInvalidRequest(f"{paper_trade_id!r} is not a valid paper trade id.")
    trade = db.get(PaperTrade, parsed_id)
    if trade is None:
        raise MarketDataInvalidRequest(f"No paper trade found with id={paper_trade_id!r}.")
    return trade


@router.post("")
def open_paper_trade(
    body: OpenPaperTradeRequest,
    market: MarketDataClient = Depends(get_market_data_client),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    recommendation = _get_recommendation_or_400(db, body.recommendation_id)
    direction = _ACTION_TO_DIRECTION.get(recommendation.action)
    if direction is None:
        raise MarketDataInvalidRequest(f"Cannot paper-trade a recommendation with action={recommendation.action!r}.")

    exchange, symbol = recommendation.symbol.split(":", 1)
    instrument_token = resolve_instrument_token(market, exchange, symbol)

    quote = market.get_quote([recommendation.symbol])
    entry_price = float(quote[recommendation.symbol]["last_price"])

    to_date = datetime.now(timezone.utc)
    from_date = to_date - timedelta(hours=_SR_LOOKBACK_HOURS)
    candles = market.get_historical_candles(instrument_token, "5minute", from_date, to_date)
    sr_context = [
        SrContextLevel(level_price=level.level_price, level_type=level.level_type)
        for level in calculate_sr_levels(candles)
    ]
    exit_rule = resolve_exit_rule(direction, entry_price, sr_context)

    negation = recommendation.rationale.get("negation", {}) if recommendation.rationale else {}
    expiry_at = None
    if negation.get("predicted_window_end"):
        try:
            expiry_at = datetime.fromisoformat(negation["predicted_window_end"])
        except ValueError:
            expiry_at = None

    founder = get_founder(db)
    trade = PaperTrade(
        recommendation_id=recommendation.id,
        user_id=founder.id,
        simulated_entry_price=entry_price,
        status="open",
        target_price=exit_rule.target_price,
        stop_loss_price=exit_rule.stop_loss_price,
        expiry_at=expiry_at,
    )

    try:
        db.add(trade)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    return {
        "id": str(trade.id),
        "recommendation_id": str(recommendation.id),
        "status": trade.status,
        "simulated_entry_price": trade.simulated_entry_price,
        "target_price": trade.target_price,
        "stop_loss_price": trade.stop_loss_price,
        "expiry_at": trade.expiry_at.isoformat() if trade.expiry_at else None,
    }


@router.post("/{paper_trade_id}/close")
def close_paper_trade(
    paper_trade_id: str,
    body: ClosePaperTradeRequest = ClosePaperTradeRequest(),
    market: MarketDataClient = Depends(get_market_data_client),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    trade = _get_paper_trade_or_400(db, paper_trade_id)
    if trade.status == "closed":
        return {"id": str(trade.id), "status": "closed", "already_closed": True, "simulated_pnl_pct": trade.simulated_pnl_pct}

    recommendation = db.get(Recommendation, trade.recommendation_id)
    direction = _ACTION_TO_DIRECTION.get(recommendation.action)

    quote = market.get_quote([recommendation.symbol])
    current_price = float(quote[recommendation.symbol]["last_price"])
    now = datetime.now(timezone.utc)

    # Numeric columns come back from Postgres as decimal.Decimal, which
    # can't mix with float in arithmetic (compute_pnl_pct's subtraction) —
    # comparisons alone (evaluate_exit) tolerate the mix, but normalize to
    # float at this boundary consistently rather than relying on that.
    target_price = float(trade.target_price)
    stop_loss_price = float(trade.stop_loss_price)
    entry_price = float(trade.simulated_entry_price)

    reason = evaluate_exit(direction, current_price, target_price, stop_loss_price, now, trade.expiry_at)
    if reason is None and not body.force:
        return {"id": str(trade.id), "status": "open", "current_price": current_price, "close_reason": None}

    trade.simulated_exit_price = current_price
    trade.simulated_pnl_pct = compute_pnl_pct(direction, entry_price, current_price)
    trade.status = "closed"
    trade.closed_at = now

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    return {
        "id": str(trade.id),
        "status": "closed",
        "close_reason": reason or "forced",
        "simulated_exit_price": trade.simulated_exit_price,
        "simulated_pnl_pct": trade.simulated_pnl_pct,
    }


@router.get("")
def list_paper_trades(
    status: str | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> dict[str, Any]:
    query = select(PaperTrade)
    if status is not None:
        query = query.where(PaperTrade.status == status)
    trades = db.execute(query.order_by(PaperTrade.opened_at.desc())).scalars().all()
    return {
        "paper_trades": [
            {
                "id": str(t.id),
                "recommendation_id": str(t.recommendation_id),
                "status": t.status,
                "simulated_entry_price": t.simulated_entry_price,
                "simulated_exit_price": t.simulated_exit_price,
                "simulated_pnl_pct": t.simulated_pnl_pct,
                "opened_at": t.opened_at.isoformat() if t.opened_at else None,
                "closed_at": t.closed_at.isoformat() if t.closed_at else None,
            }
            for t in trades
        ]
    }
