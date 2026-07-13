"""Seed a default risk_settings row for the founder user.

Phase 7 Pass 2b: risk_settings existed in database/schema.sql since Phase 1
but had no ORM model, no route, and nothing read it — VIX regime was
computed entirely from src/config.py's env-var defaults everywhere
(src/market_data/vix.py, every call site). This migration seeds the row
src/db/risk_settings.py's resolver will now prefer over those env
defaults, using the exact same starting values (docs/assumptions.md #7)
so behavior doesn't silently change the moment this ships — the row is
there for the founder to edit going forward, not to change today's
regime classification out from under them.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from sqlalchemy.dialects.postgresql import ENUM as PGEnum

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FOUNDER_USER_ID = "00000000-0000-0000-0000-000000000001"  # seeded by migration 0004

_execution_mode_enum = PGEnum("paper", "live_manual", name="execution_mode", create_type=False)

_risk_settings_table = sa.table(
    "risk_settings",
    sa.column("user_id", sa.Uuid),
    sa.column("vix_normal_max", sa.Numeric(5, 2)),
    sa.column("vix_elevated_max", sa.Numeric(5, 2)),
    sa.column("vix_high_max", sa.Numeric(5, 2)),
    sa.column("suppress_tactical_on_extreme", sa.Boolean),
    sa.column("expiry_day_dampening", sa.Boolean),
    sa.column("max_daily_recommendations", sa.Integer),
    sa.column("execution_mode", _execution_mode_enum),
)


def upgrade() -> None:
    op.bulk_insert(
        _risk_settings_table,
        [
            {
                "user_id": FOUNDER_USER_ID,
                "vix_normal_max": 15.0,
                "vix_elevated_max": 20.0,
                "vix_high_max": 30.0,
                "suppress_tactical_on_extreme": True,
                "expiry_day_dampening": True,
                "max_daily_recommendations": 20,
                "execution_mode": "paper",
            }
        ],
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM risk_settings WHERE user_id = '{FOUNDER_USER_ID}'")
