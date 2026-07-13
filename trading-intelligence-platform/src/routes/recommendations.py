"""On-demand recommendation route (F4.1-F4.4).

Chains the Phase 3 engine (pattern detection, negation, support/resistance)
with Phase 4's scoring (heavyweight correlation, confidence/risk/conviction)
and Claude narration into one persisted, explained recommendation. Same
Phase-3/4-stand-in caveat as src/routes/scan.py: this is an on-demand
trigger, not the scheduled `worker` service — repeated calls with
overlapping windows can persist duplicate rows.

Only Tactical (a detected candlestick pattern on a supported timeframe) and
Impulse (an outlier-sized move on the 5m feed) categories are reachable
here — see src/engine/recommendations.py for why Strategic/BTST aren't yet.

No route here places, modifies, or cancels a broker order — see
docs/CLAUDE.md section 2. entry/exit/strike stay unset (see
src/engine/recommendations.py's docstring): action is a directional CE/PE
proxy only, never a specific instrument to trade.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.alerts.dispatcher import dispatch_alerts
from src.config import Settings, get_settings
from src.db.models import Recommendation, SectorIndexRecord, WatchlistConstituent
from src.db.session import get_db
from src.engine.aggregation import resample_candles
from src.engine.correlation import score_correlation
from src.engine.indicators import compute_rsi
from src.engine.negation import predict_negation
from src.engine.patterns import detect_patterns
from src.engine.recommendations import build_recommendation
from src.engine.scoring import SrContextLevel
from src.engine.seasonality import detect_impulse_move
from src.engine.support_resistance import calculate_sr_levels
from src.llm.narration import narrate_rationale
from src.market_data.base import MarketDataClient
from src.market_data.exceptions import MarketDataInvalidRequest
from src.market_data.factory import get_market_data_client
from src.market_data.instruments import resolve_instrument_token
from src.market_data.vix import compute_vix_regime

router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendations"])

MIN_CANDLES_FOR_RECOMMENDATION = 20
_LOOKBACK_HOURS = 8
_CORRELATION_LOOKBACK_HOURS = 1
_ALLOWED_TIMEFRAMES = {"15m", "30m", "1h", "2h"}


def _fetch_constituent_candles(
    market: MarketDataClient, exchange: str, symbols: list[str], from_date: datetime, to_date: datetime
) -> dict[str, list[dict]]:
    """Best-effort: a symbol not resolvable in the current data mode/watchlist
    config is skipped, not a hard failure — src/engine/correlation.py's
    score_correlation already treats "no data" as excluded, not disagreement.
    """
    result = {}
    for symbol in symbols:
        try:
            token = resolve_instrument_token(market, exchange, symbol)
        except MarketDataInvalidRequest:
            continue
        result[symbol] = market.get_historical_candles(token, "5minute", from_date, to_date)
    return result


@router.post("/{symbol}")
def create_recommendation(
    symbol: str,
    exchange: str = "NSE",
    timeframe: str = "15m",
    market: MarketDataClient = Depends(get_market_data_client),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    if timeframe not in _ALLOWED_TIMEFRAMES:
        raise MarketDataInvalidRequest(
            f"timeframe={timeframe!r} not supported for a recommendation — use one of {sorted(_ALLOWED_TIMEFRAMES)}."
        )

    kite_symbol = f"{exchange}:{symbol}"
    instrument_token = resolve_instrument_token(market, exchange, symbol)

    to_date = datetime.now(timezone.utc)
    from_date = to_date - timedelta(hours=_LOOKBACK_HOURS)
    base_candles = market.get_historical_candles(instrument_token, "5minute", from_date, to_date)
    if len(base_candles) < MIN_CANDLES_FOR_RECOMMENDATION:
        raise MarketDataInvalidRequest(
            f"Only {len(base_candles)} 5m candles available for {kite_symbol} — "
            f"need at least {MIN_CANDLES_FOR_RECOMMENDATION}."
        )

    vix_quote = market.get_quote(["NSE:INDIA VIX"])
    vix_value = float(vix_quote["NSE:INDIA VIX"]["last_price"])
    vix_regime = compute_vix_regime(vix_value, settings)

    impulse = detect_impulse_move(base_candles)
    if impulse is not None:
        pattern_type, direction, used_timeframe, bar_ts, is_impulse = "impulse", impulse.direction, "5m", impulse.bar_ts, True
        working_candles = base_candles
    else:
        working_candles = resample_candles(base_candles, timeframe)
        detected = detect_patterns(working_candles)
        if not detected:
            return {
                "symbol": kite_symbol,
                "data_mode": settings.data_mode,
                "vix_regime": vix_regime,
                "recommendation": None,
                "message": "No pattern or impulse move detected in the current lookback window.",
            }
        pattern = detected[-1]  # most recent
        pattern_type, direction, used_timeframe, bar_ts, is_impulse = (
            pattern.pattern_type, pattern.direction, timeframe, pattern.bar_ts, False,
        )

    current_price = working_candles[-1]["close"]
    negation_estimate = predict_negation(pattern_type, used_timeframe, vix_regime, bar_ts)
    rsi = compute_rsi(working_candles)
    sr_context = [
        SrContextLevel(level_price=level.level_price, level_type=level.level_type)
        for level in calculate_sr_levels(working_candles)
    ]

    active_constituents = db.execute(
        select(WatchlistConstituent.symbol).where(WatchlistConstituent.is_active.is_(True))
    ).scalars().all()
    active_sectors = db.execute(
        select(SectorIndexRecord.symbol).where(SectorIndexRecord.is_active.is_(True))
    ).scalars().all()

    corr_to = datetime.now(timezone.utc)
    corr_from = corr_to - timedelta(hours=_CORRELATION_LOOKBACK_HOURS)
    constituent_candles = _fetch_constituent_candles(
        market, exchange, list(active_constituents) + list(active_sectors), corr_from, corr_to
    )
    correlation_score, correlation_breakdown = score_correlation(direction, constituent_candles)

    draft = build_recommendation(
        pattern_type=pattern_type,
        direction=direction,
        timeframe=used_timeframe,
        bar_ts=bar_ts,
        current_price=current_price,
        sr_levels=sr_context,
        correlation_score=correlation_score,
        correlation_breakdown=correlation_breakdown,
        rsi=rsi,
        vix_regime=vix_regime,
        is_impulse=is_impulse,
        negation_estimate=negation_estimate,
    )
    draft.rationale["narrative"] = narrate_rationale(kite_symbol, draft.rationale, settings)

    row = Recommendation(
        category=draft.category,
        symbol=kite_symbol,
        action=draft.action,
        forecast_horizon=draft.forecast_horizon,
        confidence_score=draft.confidence_score,
        risk_score=draft.risk_score,
        conviction_score=draft.conviction_score,
        rationale=draft.rationale,
        vix_regime_at_creation=vix_regime,
    )
    db.add(row)
    db.flush()  # populate row.id (default=uuid.uuid4 fires at flush, not construction) for the AlertLog FK below
    # Dispatched before commit so the Recommendation + every AlertLog row
    # (one per channel — F6.2) land in the same transaction. Delivery
    # failures never raise here: dispatch_alerts records dispatch_status
    # honestly per channel and always returns, so a missing Telegram/SMTP
    # config never blocks a valid, fully-scored recommendation from saving.
    alert_logs = dispatch_alerts(row, db, settings)

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    return {
        "symbol": kite_symbol,
        "data_mode": settings.data_mode,
        "vix_regime": vix_regime,
        "recommendation": {
            "id": str(row.id),
            "category": draft.category,
            "action": draft.action,
            "forecast_horizon": draft.forecast_horizon,
            "confidence_score": draft.confidence_score,
            "risk_score": draft.risk_score,
            "conviction_score": draft.conviction_score,
            "rationale": draft.rationale,
        },
        "alerts": [{"channel": log.channel, "dispatch_status": log.dispatch_status} for log in alert_logs],
    }


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
) -> dict[str, Any]:
    query = select(Recommendation).order_by(Recommendation.created_at.desc()).limit(limit)
    if category is not None:
        query = query.where(Recommendation.category == category)
    if status is not None:
        query = query.where(Recommendation.status == status)

    rows = db.execute(query).scalars().all()
    return {"recommendations": [_serialize_recommendation_summary(row) for row in rows]}


@router.get("/{recommendation_id}")
def get_recommendation(recommendation_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
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
