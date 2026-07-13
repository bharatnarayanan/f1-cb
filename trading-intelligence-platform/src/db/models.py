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
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, Uuid
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
