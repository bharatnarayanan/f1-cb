"""Seed a default founder user + BVWR as the first Strategy Marketplace entry.

Phase 5 (Strategy Marketplace): strategies.created_by is a NOT NULL FK to
users(id), but no login/auth routes exist yet (that's a separate, unbuilt
phase) — confirmed with the user before building: seed one default founder
user rather than build auth now. Password is a random, never-used value
(bcrypt-hashed per docs/CLAUDE.md section 3 — never plaintext); there is no
login endpoint that could authenticate with it yet.

BVWR (the founder's own Breakout VWAP Retracement rule) is seeded using the
exact canonical_logic already hand-authored in docs/strategy_schema.json's
`examples` — no extraction needed for this one, it's the schema's own
worked example. source_type='user_rule', status='extracted' (ready to
backtest via the API; migrations don't call live backtest logic).

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-13
"""

import uuid
from typing import Sequence, Union

import bcrypt
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PGEnum

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FOUNDER_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
FOUNDER_EMAIL = "founder@local"
BVWR_STRATEGY_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")

_BVWR_CANONICAL_LOGIC = {
    "version": "1.0",
    "instrument": {
        "underlying": "NIFTY",
        "leg": "either",
        "moneyness": "ITM",
        "price_band": {"min": 350, "max": 450},
    },
    "timeframe": "10m",
    "pattern_trigger": {"pattern_type": "three_inside", "breakout_offset_points": 7},
    "time_filters": [
        {"rule": "ignore_before", "time": "10:30", "note": "Ignore breakout in first 10 minutes; wait for retracement."},
        {"rule": "retry_window", "time": "13:35", "note": "If no breakout by 11:00, trade after 13:35 or 14:35."},
    ],
    "entry": {
        "logic": "AND",
        "retracement_reference": "vwap_option",
        "conditions": [
            {"left": {"field": "close"}, "operator": ">", "right": {"indicator": "SMA", "period": 50}},
            {"left": {"field": "close"}, "operator": ">", "right": {"indicator": "VWAP", "period": 1}},
            {
                "left": {"field": "close"},
                "operator": ">",
                "right": {"indicator": "SUPERTREND", "period": 7, "params": {"multiplier": 3}},
            },
        ],
    },
    "exit": {
        "targets": [{"type": "prior_candle_high"}, {"type": "day_high"}, {"type": "supertrend_line"}],
        "stop_loss": {"type": "below_ma", "reference_indicator": {"indicator": "SMA", "period": 50}},
    },
    "guards": [{"left": {"field": "close"}, "operator": ">", "right": {"indicator": "SMA", "period": 50}}],
    "is_preset": True,
}

_users_table = sa.table(
    "users",
    sa.column("id", sa.Uuid),
    sa.column("email", sa.Text),
    sa.column("hashed_password", sa.Text),
    sa.column("display_name", sa.Text),
)

# source_type/status are Postgres enum columns (strategy_source_type,
# strategy_status from database/schema.sql) — bound as plain sa.Text, psycopg
# sends an explicit ::VARCHAR cast that Postgres then rejects against the
# real enum column, same class of bug src/db/models.py's AuditLog comment
# already documents for UUID columns.
_strategy_source_type_enum = PGEnum(
    "video", "text", "pseudocode", "pine_script", "user_rule",
    name="strategy_source_type", create_type=False,
)
_strategy_status_enum = PGEnum(
    "ingested", "extracted", "backtested", "usable", "rejected",
    name="strategy_status", create_type=False,
)

_strategies_table = sa.table(
    "strategies",
    sa.column("id", sa.Uuid),
    sa.column("name", sa.Text),
    sa.column("source_type", _strategy_source_type_enum),
    sa.column("raw_input", sa.Text),
    sa.column("canonical_logic", sa.JSON),
    sa.column("status", _strategy_status_enum),
    sa.column("created_by", sa.Uuid),
)


def upgrade() -> None:
    placeholder_hash = bcrypt.hashpw(uuid.uuid4().bytes, bcrypt.gensalt()).decode("ascii")

    op.bulk_insert(
        _users_table,
        [
            {
                "id": FOUNDER_USER_ID,
                "email": FOUNDER_EMAIL,
                "hashed_password": placeholder_hash,
                "display_name": "Founder",
            }
        ],
    )
    op.bulk_insert(
        _strategies_table,
        [
            {
                "id": BVWR_STRATEGY_ID,
                "name": "Breakout VWAP Retracement (BVWR)",
                "source_type": "user_rule",
                "raw_input": None,
                "canonical_logic": _BVWR_CANONICAL_LOGIC,
                "status": "extracted",
                "created_by": FOUNDER_USER_ID,
            }
        ],
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM strategies WHERE id = '{BVWR_STRATEGY_ID}'")
    op.execute(f"DELETE FROM users WHERE id = '{FOUNDER_USER_ID}'")
