"""Add expiry_weekday to risk_settings.

Phase 8 (F8.1, guardrail enforcement). NIFTY's weekly options expiry
weekday has changed before and isn't something to hardcode as a fixed
fact — this is a founder-editable setting instead (default 1 = Tuesday,
Python's date.weekday() convention: Monday=0 ... Sunday=6), used by
src/engine/risk_guardrails.py's is_expiry_day() check. ADD COLUMN with a
server default backfills the existing seeded row (migration 0006)
automatically.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "risk_settings",
        sa.Column("expiry_weekday", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("risk_settings", "expiry_weekday")
