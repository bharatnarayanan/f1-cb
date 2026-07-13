"""Add target_price/stop_loss_price/expiry_at to paper_trades.

F6.1 (Paper-trading simulator). The original schema.sql paper_trades table
predates a rule-based exit — these three nullable columns lock in the exit
rule at OPEN time (src/engine/paper_trading.py resolves them from Phase 3's
support/resistance levels + Phase 3's negation-window prediction).
Recomputing them fresh on every close call instead would let the
target/stop silently drift between open and close, which no real trade
does — see docs/assumptions.md.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("paper_trades", sa.Column("target_price", sa.Numeric(12, 2), nullable=True))
    op.add_column("paper_trades", sa.Column("stop_loss_price", sa.Numeric(12, 2), nullable=True))
    op.add_column("paper_trades", sa.Column("expiry_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("paper_trades", "expiry_at")
    op.drop_column("paper_trades", "stop_loss_price")
    op.drop_column("paper_trades", "target_price")
