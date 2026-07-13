"""ORM models for the tables Phase 2 code actually touches.

Every other table in database/schema.sql (patterns_detected, recommendations,
strategies, ...) stays schema-only until the phase that builds routes/jobs
against it defines its ORM model — see docs/CLAUDE.md's "small, testable
modules" convention and docs/assumptions.md for why this file doesn't mirror
the full schema yet.

audit_log is append-only (docs/CLAUDE.md section 3): no update()/delete()
helper is defined anywhere against this model, on purpose.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Numeric, String, Uuid
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
