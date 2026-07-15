"""Strategy Marketplace routes (F5.1-F5.5).

Ingest -> extract -> independently backtest -> export/fuse. No route here
places, modifies, or cancels a broker order — Pine Script export is text
the founder pastes into TradingView themselves, never pushed live (no such
public API exists — docs/CLAUDE.md section 4). See docs/CLAUDE.md section 2.
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
from src.db.models import Strategy, StrategyBacktest, StrategyFusion, User
from src.db.session import get_db
from src.engine.backtest import run_backtest
from src.engine.fusion import fuse_strategies
from src.engine.pine_export import export_to_pine_script
from src.llm.exceptions import ExtractionUnavailable
from src.llm.extraction import extract_canonical_logic
from src.market_data.base import MarketDataClient
from src.market_data.exceptions import MarketDataInvalidRequest
from src.market_data.factory import get_market_data_client
from src.market_data.instruments import resolve_instrument_token
from src.metrics import backtests_run_total

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])

_UNDERLYING_TO_KITE_SYMBOL = {"NIFTY": "NIFTY 50", "BANKNIFTY": "NIFTY BANK"}
_BACKTEST_LOOKBACK_DAYS = 5


class IngestStrategyRequest(BaseModel):
    name: str
    source_type: str  # "text" | "pseudocode" | "pine_script" | "video"
    raw_input: str
    source_ref: str | None = None  # video URL, if source_type == "video"


class FuseStrategiesRequest(BaseModel):
    name: str
    base_strategy_id: str
    other_strategy_id: str


def _get_strategy_or_400(db: Session, strategy_id: str) -> Strategy:
    try:
        parsed_id = uuid.UUID(strategy_id)
    except ValueError:
        raise MarketDataInvalidRequest(f"{strategy_id!r} is not a valid strategy id.")

    strategy = db.get(Strategy, parsed_id)
    if strategy is None:
        raise MarketDataInvalidRequest(f"No strategy found with id={strategy_id!r}.")
    return strategy


@router.post("")
def ingest_strategy(
    body: IngestStrategyRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    if body.source_type not in ("text", "pseudocode", "pine_script", "video"):
        raise MarketDataInvalidRequest(f"unsupported source_type={body.source_type!r}")

    founder = get_founder(db)
    strategy = Strategy(
        name=body.name,
        source_type=body.source_type,
        source_ref=body.source_ref,
        raw_input=body.raw_input,
        status="ingested",
        created_by=founder.id,
    )

    try:
        canonical_logic = extract_canonical_logic(body.raw_input, settings)
        strategy.canonical_logic = canonical_logic
        strategy.status = "extracted"
    except ExtractionUnavailable as exc:
        # A strategy can be ingested (and reviewed later) even if extraction
        # can't run right now — but it stays `ingested`, never silently
        # marked ready, since there's no canonical_logic to backtest yet.
        strategy.status = "ingested"
        extraction_error = str(exc)
    else:
        extraction_error = None

    try:
        db.add(strategy)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    return {
        "id": str(strategy.id),
        "name": strategy.name,
        "status": strategy.status,
        "canonical_logic": strategy.canonical_logic,
        "extraction_error": extraction_error,
    }


@router.get("")
def list_strategies(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict[str, Any]:
    strategies = db.execute(select(Strategy).order_by(Strategy.created_at.desc())).scalars().all()
    return {
        "strategies": [
            {"id": str(s.id), "name": s.name, "source_type": s.source_type, "status": s.status}
            for s in strategies
        ]
    }


@router.get("/{strategy_id}")
def get_strategy(
    strategy_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> dict[str, Any]:
    strategy = _get_strategy_or_400(db, strategy_id)
    return {
        "id": str(strategy.id),
        "name": strategy.name,
        "source_type": strategy.source_type,
        "status": strategy.status,
        "canonical_logic": strategy.canonical_logic,
    }


@router.post("/{strategy_id}/backtest")
def backtest_strategy(
    strategy_id: str,
    db: Session = Depends(get_db),
    market: MarketDataClient = Depends(get_market_data_client),
    settings: Settings = Depends(get_settings),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    strategy = _get_strategy_or_400(db, strategy_id)
    if strategy.canonical_logic is None:
        raise MarketDataInvalidRequest(
            f"Strategy {strategy_id} has no canonical_logic yet (status={strategy.status!r}) — extract it first."
        )

    underlying = strategy.canonical_logic["instrument"]["underlying"]
    kite_symbol = _UNDERLYING_TO_KITE_SYMBOL.get(underlying)
    if kite_symbol is None:
        raise MarketDataInvalidRequest(f"unsupported underlying={underlying!r}")

    instrument_token = resolve_instrument_token(market, "NSE", kite_symbol)
    to_date = datetime.now(timezone.utc)
    from_date = to_date - timedelta(days=_BACKTEST_LOOKBACK_DAYS)
    candles = market.get_historical_candles(instrument_token, "5minute", from_date, to_date)

    try:
        result = run_backtest(strategy.canonical_logic, candles)
    except ValueError as exc:
        raise MarketDataInvalidRequest(str(exc)) from exc

    backtest_row = StrategyBacktest(
        strategy_id=strategy.id,
        date_from=from_date.date(),
        date_to=to_date.date(),
        win_rate_pct=result.win_rate_pct,
        sharpe_ratio=result.sharpe_ratio,
        max_drawdown_pct=result.max_drawdown_pct,
        total_return_pct=result.total_return_pct,
        confidence_score=result.confidence_score,
        trade_log=result.trade_log,
    )
    strategy.status = "backtested" if result.num_trades > 0 else strategy.status

    try:
        db.add(backtest_row)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    backtests_run_total.inc()

    return {
        "strategy_id": strategy_id,
        "data_mode": settings.data_mode,
        "num_trades": result.num_trades,
        "win_rate_pct": result.win_rate_pct,
        "sharpe_ratio": result.sharpe_ratio,
        "max_drawdown_pct": result.max_drawdown_pct,
        "total_return_pct": result.total_return_pct,
        "confidence_score": result.confidence_score,
        "trade_log": result.trade_log,
        "assumptions": result.assumptions,
    }


@router.post("/fuse")
def fuse(
    body: FuseStrategiesRequest, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> dict[str, Any]:
    base = _get_strategy_or_400(db, body.base_strategy_id)
    other = _get_strategy_or_400(db, body.other_strategy_id)
    if base.canonical_logic is None or other.canonical_logic is None:
        raise MarketDataInvalidRequest("both strategies need canonical_logic (extract them first) before fusing.")

    try:
        resolved_logic = fuse_strategies(base.canonical_logic, other.canonical_logic)
    except ValueError as exc:
        raise MarketDataInvalidRequest(str(exc)) from exc

    founder = get_founder(db)
    fused_strategy = Strategy(
        name=body.name,
        source_type="user_rule",
        raw_input=None,
        canonical_logic=resolved_logic,
        status="extracted",
        created_by=founder.id,
    )
    db.add(fused_strategy)
    db.flush()  # populate fused_strategy.id for the FK below

    fusion_row = StrategyFusion(
        parent_strategy_ids=[base.id, other.id],
        resolved_logic=resolved_logic,
        fused_strategy_id=fused_strategy.id,
    )

    try:
        db.add(fusion_row)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    return {"fused_strategy_id": str(fused_strategy.id), "resolved_logic": resolved_logic}


@router.get("/{strategy_id}/export")
def export_strategy(
    strategy_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> dict[str, Any]:
    strategy = _get_strategy_or_400(db, strategy_id)
    if strategy.canonical_logic is None:
        raise MarketDataInvalidRequest(f"Strategy {strategy_id} has no canonical_logic yet — extract it first.")

    return {"strategy_id": strategy_id, "pine_script": export_to_pine_script(strategy.canonical_logic, strategy.name)}
