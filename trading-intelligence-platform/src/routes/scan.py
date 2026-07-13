"""On-demand core-engine scan route (F3.1-F3.4).

Chains pattern detection -> negation prediction -> support/resistance
across a small set of timeframes for one symbol, and persists every result.
This is a Phase 3 stand-in for the scheduled `worker` service described in
docs/architecture.md (not built yet, same pattern as src/routes/market.py's
on-demand /vix route standing in for scheduled VIX ingestion) — see
docs/assumptions.md.

Because this is on-demand rather than triggered strictly on new candle
closes, calling it repeatedly with overlapping lookback windows CAN persist
duplicate pattern/SR rows for bars already scanned. Acceptable for a Phase 3
demonstration; the real worker will dedupe by only ever scanning the newest
closed candle. Do not build production polling against this route as-is.

Every route here reads market data or writes deterministic, structured
computations — no route places, modifies, or cancels a broker order. See
docs/CLAUDE.md section 2.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.config import Settings, get_settings
from src.db.models import NegationPrediction, PatternDetected, SrLevelRecord
from src.db.session import get_db
from src.engine.aggregation import resample_candles
from src.engine.negation import predict_negation
from src.engine.patterns import detect_patterns
from src.engine.support_resistance import calculate_sr_levels
from src.market_data.base import MarketDataClient
from src.market_data.exceptions import MarketDataInvalidRequest
from src.market_data.factory import get_market_data_client
from src.market_data.instruments import resolve_instrument_token
from src.market_data.vix import compute_vix_regime

router = APIRouter(prefix="/api/v1/scan", tags=["scan"])

SCAN_TIMEFRAMES = ["5m", "15m", "1h"]
MIN_CANDLES_FOR_SCAN = 20
_LOOKBACK_HOURS = 8


@router.post("/{symbol}")
def run_scan(
    symbol: str,
    exchange: str = "NSE",
    market: MarketDataClient = Depends(get_market_data_client),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    kite_symbol = f"{exchange}:{symbol}"
    instrument_token = resolve_instrument_token(market, exchange, symbol)

    to_date = datetime.now(timezone.utc)
    from_date = to_date - timedelta(hours=_LOOKBACK_HOURS)
    base_candles = market.get_historical_candles(instrument_token, "5minute", from_date, to_date)
    if len(base_candles) < MIN_CANDLES_FOR_SCAN:
        raise MarketDataInvalidRequest(
            f"Only {len(base_candles)} 5m candles available for {kite_symbol} — "
            f"need at least {MIN_CANDLES_FOR_SCAN} to run a scan."
        )

    vix_quote = market.get_quote(["NSE:INDIA VIX"])
    vix_value = float(vix_quote["NSE:INDIA VIX"]["last_price"])
    vix_regime = compute_vix_regime(vix_value, settings)

    patterns_out: list[dict] = []
    negations_out: list[dict] = []
    sr_out: list[dict] = []

    for timeframe in SCAN_TIMEFRAMES:
        tf_candles = resample_candles(base_candles, timeframe)

        for pattern in detect_patterns(tf_candles):
            pattern_row = PatternDetected(
                symbol=kite_symbol,
                timeframe=timeframe,
                pattern_type=pattern.pattern_type,
                direction=pattern.direction,
                bar_ts=pattern.bar_ts,
            )
            db.add(pattern_row)
            db.flush()  # populate pattern_row.id for the negation FK below

            estimate = predict_negation(pattern.pattern_type, timeframe, vix_regime, pattern.bar_ts)
            db.add(
                NegationPrediction(
                    pattern_id=pattern_row.id,
                    model_version=estimate.model_version,
                    predicted_candles=estimate.predicted_candles,
                    predicted_window_start=estimate.predicted_window_start,
                    predicted_window_end=estimate.predicted_window_end,
                    vix_regime_at_prediction=vix_regime,
                )
            )

            patterns_out.append(
                {
                    "timeframe": timeframe,
                    "pattern_type": pattern.pattern_type,
                    "direction": pattern.direction,
                    "bar_ts": pattern.bar_ts.isoformat(),
                }
            )
            negations_out.append(
                {
                    "timeframe": timeframe,
                    "pattern_type": pattern.pattern_type,
                    "model_version": estimate.model_version,
                    "predicted_candles": estimate.predicted_candles,
                    "predicted_window_end": estimate.predicted_window_end.isoformat(),
                }
            )

        for level in calculate_sr_levels(tf_candles):
            db.add(
                SrLevelRecord(
                    symbol=kite_symbol,
                    timeframe=timeframe,
                    level_price=level.level_price,
                    level_type=level.level_type,
                    hit_count=level.hit_count,
                    confluence_score=level.confluence_score,
                    last_hit_ts=level.last_hit_ts,
                )
            )
            sr_out.append(
                {
                    "timeframe": timeframe,
                    "level_price": level.level_price,
                    "level_type": level.level_type,
                    "hit_count": level.hit_count,
                    "confluence_score": level.confluence_score,
                }
            )

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    return {
        "symbol": kite_symbol,
        "data_mode": settings.data_mode,
        "vix_regime": vix_regime,
        "candles_scanned": len(base_candles),
        "patterns_detected": patterns_out,
        "negation_predictions": negations_out,
        "sr_levels": sr_out,
    }
