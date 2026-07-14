"""Recommendation pipeline (F4.1-F4.4 orchestration) — extracted from
src/routes/recommendations.py (Phase 8, worker service pass) so the
scheduled `worker` service and the on-demand HTTP route share one
implementation instead of the worker reimplementing this by hand.

This module does real I/O (DB, market data, Claude narration, alert
dispatch) — unlike src/engine/*, which is pure deterministic computation
over already-fetched data (docs/CLAUDE.md section 3). Keeping the two
separate is why src/engine/recommendations.py's build_recommendation stays
untouched here; this module is the thing that calls it.

Only Tactical (a detected candlestick pattern on a supported timeframe) and
Impulse (an outlier-sized move on the 5m feed) categories are reachable
here — see src/engine/recommendations.py for why Strategic/BTST aren't yet.

No function here places, modifies, or cancels a broker order — see
docs/CLAUDE.md section 2. entry/exit/strike stay unset (see
src/engine/recommendations.py's docstring): action is a directional CE/PE
proxy only, never a specific instrument to trade.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.alerts.dispatcher import dispatch_alerts
from src.cache.redis_client import RedisCache
from src.config import Settings
from src.db.models import Recommendation, SectorIndexRecord, WatchlistConstituent
from src.db.risk_settings import get_guardrail_settings, get_vix_thresholds
from src.engine.aggregation import resample_candles
from src.engine.correlation import score_correlation
from src.engine.indicators import compute_rsi
from src.engine.negation import predict_negation
from src.engine.patterns import detect_patterns
from src.engine.recommendations import build_recommendation
from src.engine.risk_guardrails import apply_expiry_dampening, is_expiry_day, should_suppress_tactical
from src.engine.scoring import SrContextLevel
from src.engine.seasonality import IST, detect_impulse_move
from src.engine.support_resistance import calculate_sr_levels
from src.llm.narration import narrate_rationale
from src.market_data.base import MarketDataClient
from src.market_data.exceptions import MarketDataInvalidRequest
from src.market_data.instruments import resolve_instrument_token
from src.market_data.vix import compute_vix_regime
from src.metrics import recommendations_created_total, recommendations_suppressed_total
from src.worker.dedup import already_scanned, mark_scanned

MIN_CANDLES_FOR_RECOMMENDATION = 20
_LOOKBACK_HOURS = 8
_CORRELATION_LOOKBACK_HOURS = 1
ALLOWED_TIMEFRAMES = {"15m", "30m", "1h", "2h"}


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


def generate_recommendation(
    symbol: str,
    exchange: str,
    timeframe: str,
    market: MarketDataClient,
    db: Session,
    settings: Settings,
    dedup_cache: RedisCache | None = None,
) -> dict:
    """Runs the full pattern -> negation -> correlation -> scoring ->
    narration -> persistence -> alert-dispatch pipeline for one symbol and
    returns the same response shape the HTTP route has always returned.
    Callable directly (no FastAPI Depends) so both
    src/routes/recommendations.py and src/worker/main.py share this one
    implementation.

    dedup_cache: only passed by the worker (src/worker/main.py). The
    on-demand HTTP route deliberately never dedupes — a founder manually
    re-triggering a scan wants a fresh evaluation even against a bar
    already looked at. The worker, evaluating on a fixed interval, does
    not want to re-persist a decision about the same closed bar on every
    tick until a newer candle closes.
    """
    if timeframe not in ALLOWED_TIMEFRAMES:
        raise MarketDataInvalidRequest(
            f"timeframe={timeframe!r} not supported for a recommendation — use one of {sorted(ALLOWED_TIMEFRAMES)}."
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
    normal_max, elevated_max, high_max = get_vix_thresholds(db, settings)
    vix_regime = compute_vix_regime(vix_value, normal_max, elevated_max, high_max)

    guardrails = get_guardrail_settings(db)
    now_ist = datetime.now(timezone.utc).astimezone(IST)
    is_expiry = is_expiry_day(now_ist.date(), guardrails.expiry_weekday)

    # Checked early (before pattern detection, correlation fetches across
    # the whole watchlist, and a Claude narration call) so hitting the cap
    # doesn't pay for work whose result gets discarded anyway.
    start_of_day_utc = now_ist.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    todays_count = db.execute(
        select(func.count()).select_from(Recommendation).where(Recommendation.created_at >= start_of_day_utc)
    ).scalar_one()
    if todays_count >= guardrails.max_daily_recommendations:
        recommendations_suppressed_total.labels(reason="daily_cap").inc()
        return {
            "symbol": kite_symbol,
            "data_mode": settings.data_mode,
            "vix_regime": vix_regime,
            "recommendation": None,
            "message": (
                f"Daily recommendation cap reached ({guardrails.max_daily_recommendations}/day) — "
                "adjust it in Settings if you want more today."
            ),
        }

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

    # Dedup as early as bar_ts is known, before the negation/correlation/
    # narration work below — mirrors the daily-cap check's "don't pay for
    # discarded work" reasoning. Marked scanned regardless of what this bar
    # eventually decides (fired or suppressed): the point is "don't
    # re-evaluate this exact closed bar again," not "don't re-suppress it."
    if dedup_cache is not None:
        if already_scanned(dedup_cache, kite_symbol, used_timeframe, bar_ts):
            return {
                "symbol": kite_symbol,
                "data_mode": settings.data_mode,
                "vix_regime": vix_regime,
                "recommendation": None,
                "message": f"Bar {bar_ts.isoformat()} on {used_timeframe} already scanned — skipping duplicate.",
            }
        mark_scanned(dedup_cache, kite_symbol, used_timeframe, bar_ts)

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

    if should_suppress_tactical(draft.category, vix_regime, guardrails.suppress_tactical_on_extreme):
        recommendations_suppressed_total.labels(reason="tactical_extreme_vix").inc()
        return {
            "symbol": kite_symbol,
            "data_mode": settings.data_mode,
            "vix_regime": vix_regime,
            "recommendation": None,
            "message": "Tactical recommendations are suppressed while VIX is in the Extreme regime.",
        }

    # draft is frozen (src/engine/recommendations.py) — the dampened value
    # is computed separately and used below rather than mutating draft.
    final_conviction_score = apply_expiry_dampening(draft.conviction_score, is_expiry, guardrails.expiry_day_dampening)
    draft.rationale["expiry_day"] = is_expiry
    if final_conviction_score != draft.conviction_score:
        draft.rationale["conviction_score_before_expiry_dampening"] = draft.conviction_score

    draft.rationale["narrative"] = narrate_rationale(kite_symbol, draft.rationale, settings)

    row = Recommendation(
        category=draft.category,
        symbol=kite_symbol,
        action=draft.action,
        forecast_horizon=draft.forecast_horizon,
        confidence_score=draft.confidence_score,
        risk_score=draft.risk_score,
        conviction_score=final_conviction_score,
        rationale=draft.rationale,
        vix_regime_at_creation=vix_regime,
        is_expiry_day=is_expiry,
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

    recommendations_created_total.labels(category=draft.category).inc()

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
            "conviction_score": final_conviction_score,
            "rationale": draft.rationale,
        },
        "alerts": [{"channel": log.channel, "dispatch_status": log.dispatch_status} for log in alert_logs],
    }
