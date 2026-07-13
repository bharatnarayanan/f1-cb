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
from datetime import datetime, time as time_type, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Time, Uuid
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
