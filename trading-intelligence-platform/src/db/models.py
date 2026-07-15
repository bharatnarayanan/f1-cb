"""ORM models for the tables application code actually touches.

Every other table in database/schema.sql (recommendations, strategies, ...)
stays schema-only until the phase that builds routes/jobs against it
defines its ORM model — see docs/CLAUDE.md's "small, testable modules"
convention and docs/assumptions.md for why this file doesn't mirror the
full schema yet.

audit_log is append-only (docs/CLAUDE.md section 3): no update()/delete()
helper is defined anywhere against this model, on purpose.
"""

import uuid
from datetime import date as date_type, datetime, time as time_type, timezone

from sqlalchemy import (
    ARRAY,
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Time,
    Uuid,
)
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    # Uuid (not String) to match schema.sql's `id UUID PRIMARY KEY` column
    # type exactly — a mismatch here makes psycopg3 send an explicit
    # ::VARCHAR cast that Postgres then rejects against the real UUID column.
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


# Matches the `vix_regime` enum type created by database/schema.sql /
# alembic/versions/0001_initial_schema.py — create_type=False so this model
# never tries to (re)create the Postgres type itself.
vix_regime_enum = PGEnum(
    "normal", "elevated", "high", "extreme",
    name="vix_regime",
    create_type=False,
)


class IndiaVixSnapshot(Base):
    __tablename__ = "india_vix_snapshots"

    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    value: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    regime: Mapped[str] = mapped_column(vix_regime_enum, nullable=False)


class PatternDetected(Base):
    __tablename__ = "patterns_detected"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    timeframe: Mapped[str] = mapped_column(String, nullable=False)
    # engulfing | three_inside | three_outside | harami | doji | pin_bar —
    # see src/engine/patterns.py, the only place this set is enumerated.
    pattern_type: Mapped[str] = mapped_column(String, nullable=False)
    direction: Mapped[str] = mapped_column(String, nullable=False)
    bar_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class NegationPrediction(Base):
    __tablename__ = "negation_predictions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    pattern_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("patterns_detected.id", ondelete="CASCADE"), nullable=False
    )
    # heuristic-v1 (src/engine/negation.py) until v1.1's LSTM model exists —
    # swappable without a migration, see database/schema.sql's comment.
    model_version: Mapped[str] = mapped_column(String, nullable=False, default="heuristic-v1")
    predicted_candles: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    predicted_window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    predicted_window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    vix_regime_at_prediction: Mapped[str] = mapped_column(vix_regime_enum, nullable=False)
    # Filled in retroactively once the outcome is observed — no code writes
    # this yet (that's the trade-journal feedback loop, a later phase).
    actual_negation_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class SrLevelRecord(Base):
    __tablename__ = "sr_levels"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    timeframe: Mapped[str] = mapped_column(String, nullable=False)
    level_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    level_type: Mapped[str] = mapped_column(String, nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    confluence_score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0)
    last_hit_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class WatchlistConstituent(Base):
    __tablename__ = "watchlist_constituents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    # Deliberately not hardcoded — see alembic/versions/0003_seed_watchlist.py.
    index_weight_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    sector: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SectorIndexRecord(Base):
    __tablename__ = "sector_indices"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SeasonalityWindowRecord(Base):
    __tablename__ = "seasonality_windows"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(String, nullable=False)
    window_start: Mapped[time_type] = mapped_column(Time, nullable=False)
    window_end: Mapped[time_type] = mapped_column(Time, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


recommendation_category_enum = PGEnum(
    "tactical", "impulse", "strategic", "btst",
    name="recommendation_category",
    create_type=False,
)

recommendation_action_enum = PGEnum(
    "BUY_CE", "BUY_PE", "SELL_CE", "SELL_PE", "NO_TRADE",
    name="recommendation_action",
    create_type=False,
)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    category: Mapped[str] = mapped_column(recommendation_category_enum, nullable=False)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    strike: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    option_type: Mapped[str | None] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(recommendation_action_enum, nullable=False)
    entry_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    stop_loss: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    target_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    forecast_horizon: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    risk_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    conviction_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    # Structured reasoning tree (factor scores/weights) + Claude's narrated
    # paragraph — see src/engine/recommendations.py / src/llm/narration.py.
    # Never the other way around: the LLM narrates this tree, it never
    # produces the scores inside it (docs/CLAUDE.md section 3).
    rationale: Mapped[dict] = mapped_column(JSON, nullable=False)
    vix_regime_at_creation: Mapped[str] = mapped_column(vix_regime_enum, nullable=False)
    is_expiry_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class User(Base):
    """No login/auth routes exist yet (docs/assumptions.md) — this model
    exists only so Phase 5's Strategy Marketplace has a valid
    strategies.created_by to reference. See
    alembic/versions/0004_seed_founder_strategy.py for the single seeded
    founder row.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


strategy_source_type_enum = PGEnum(
    "video", "text", "pseudocode", "pine_script", "user_rule",
    name="strategy_source_type",
    create_type=False,
)

strategy_status_enum = PGEnum(
    "ingested", "extracted", "backtested", "usable", "rejected",
    name="strategy_status",
    create_type=False,
)


class Strategy(Base):
    __tablename__ = "strategies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[str] = mapped_column(strategy_source_type_enum, nullable=False)
    # Video URL, or null for text/pseudocode/Pine Script entered inline.
    source_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_input: Mapped[str | None] = mapped_column(String, nullable=True)
    # Structured rule set matching docs/strategy_schema.json — see
    # src/llm/extraction.py (populates this) and
    # src/engine/strategy_interpreter.py (consumes it).
    canonical_logic: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(strategy_status_enum, nullable=False, default="ingested")
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class StrategyBacktest(Base):
    __tablename__ = "strategy_backtests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False
    )
    date_from: Mapped[date_type] = mapped_column(Date, nullable=False)
    date_to: Mapped[date_type] = mapped_column(Date, nullable=False)
    win_rate_pct: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    sharpe_ratio: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    max_drawdown_pct: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    total_return_pct: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    # 0-100, independent-backtest-derived — see src/engine/backtest.py's
    # documented confidence formula (no formula exists anywhere in spec).
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    trade_log: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class StrategyFusion(Base):
    __tablename__ = "strategy_fusion"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    parent_strategy_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid), nullable=False)
    resolved_logic: Mapped[dict] = mapped_column(JSON, nullable=False)
    fused_strategy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("recommendations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    simulated_entry_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    simulated_exit_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    simulated_pnl_pct: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    # Locked in at open time (migration 0005) — the exit rule this trade
    # will be checked against on close. Not in the original schema.sql
    # (paper_trades predates a rule-based exit); recomputing fresh on every
    # close call instead would let the target/stop silently drift between
    # open and close, which no real trade does — see
    # src/engine/paper_trading.py's module docstring.
    target_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    stop_loss_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    expiry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TradeJournalEntry(Base):
    __tablename__ = "trade_journal"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    recommendation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    outcome: Mapped[str] = mapped_column(String, nullable=False)  # win | loss | breakeven | not_taken
    realized_pnl_pct: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    observation: Mapped[str | None] = mapped_column(String, nullable=True)
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


dispatch_status_enum = PGEnum(
    "pending", "sent", "failed",
    name="dispatch_status",
    create_type=False,
)


class AlertLog(Base):
    __tablename__ = "alerts_log"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("recommendations.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String, nullable=False)  # telegram | email | dashboard
    dispatch_status: Mapped[str] = mapped_column(dispatch_status_enum, nullable=False, default="pending")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


execution_mode_enum = PGEnum(
    "paper", "live_manual",
    name="execution_mode",
    create_type=False,
)


class RiskSettings(Base):
    """One row per user (Phase 7 Pass 2b) — src/db/risk_settings.py resolves
    this row's VIX thresholds in preference to the env-var defaults in
    src/config.py wherever VIX regime is computed, so the settings screen
    actually controls behavior rather than just displaying a number nobody
    reads. execution_mode is constrained to exactly 'paper'/'live_manual'
    at the DB enum level AND validated again at the API layer
    (src/routes/settings.py) — docs/CLAUDE.md section 2 never allows a
    third auto-execute mode (no live_algo, ever), even behind a setting.
    """

    __tablename__ = "risk_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    vix_normal_max: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=15.0)
    vix_elevated_max: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=20.0)
    vix_high_max: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=30.0)
    suppress_tactical_on_extreme: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    expiry_day_dampening: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Founder-editable (migration 0007, Phase 8) rather than a hardcoded
    # assumption about NSE's current weekly-expiry weekday — that's
    # changed before and isn't something to bake in as a guessed fact.
    # Python's date.weekday(): Monday=0 ... Sunday=6. Default 1 = Tuesday.
    expiry_weekday: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_daily_recommendations: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    execution_mode: Mapped[str] = mapped_column(execution_mode_enum, nullable=False, default="paper")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class FactorWeight(Base):
    """One row per src/engine/scoring.py CONFIDENCE_WEIGHTS factor
    (migration 0008) — src/db/factor_weights.py resolves current weights
    from here in preference to the hardcoded CONFIDENCE_WEIGHTS constant.
    alpha/beta are Beta-Bernoulli posterior parameters
    (src/engine/weight_update.py) updated from trade_journal outcomes by
    recompute_factor_weights; weight is the resulting (clamped) posterior
    mean. Never touched by the LLM — a deterministic computation over
    structured win/loss counts (docs/CLAUDE.md section 3).
    """

    __tablename__ = "factor_weights"

    factor_name: Mapped[str] = mapped_column(String, primary_key=True)
    weight: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    alpha: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    beta: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
