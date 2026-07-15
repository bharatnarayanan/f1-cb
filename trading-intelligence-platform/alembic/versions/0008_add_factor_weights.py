"""Create factor_weights table, seeded from the CONFIDENCE_WEIGHTS constant.

CLAUDE.md item 9: "Trade-journal feedback loop -> Bayesian weight-update
job." src/engine/scoring.py's CONFIDENCE_WEIGHTS has been a hardcoded
module constant since Phase 4 — this table is what the new job
(src/db/factor_weights.py's recompute_factor_weights) actually updates,
one row per confidence factor. Seeded with today's exact constant values
so live behavior doesn't change the moment this ships — same "behavior
doesn't silently change" posture as migration 0006.

alpha/beta are the Beta-Bernoulli posterior parameters (see
src/engine/weight_update.py) — seeded per-factor so each prior's mean
equals that factor's own CONFIDENCE_WEIGHTS default (10 pseudo-
observations total, split proportionally: e.g. macro_sr_alignment's 0.25
becomes alpha=2.5/beta=7.5), NOT a flat alpha=beta=5 shared by every
factor. A flat shared prior means every factor's mean is 0.5, which would
silently reset a zero-evidence factor's weight the moment
recompute_factor_weights ever runs on it — even with no real trade
history touching it. Per-factor priors keep the founder's original
CONFIDENCE_WEIGHTS defaults intact until real evidence actually exists for
that specific factor.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PRIOR_STRENGTH = 10.0

# Mirrors src/engine/scoring.py's CONFIDENCE_WEIGHTS exactly.
_SEED_WEIGHTS = {
    "macro_sr_alignment": 0.25,
    "heavyweight_pattern_alignment": 0.25,
    "strike_candle_pattern": 0.20,
    "oi_accumulation": 0.15,
    "rsi_alignment": 0.15,
}

_factor_weights_table = sa.table(
    "factor_weights",
    sa.column("factor_name", sa.String),
    sa.column("weight", sa.Numeric(5, 4)),
    sa.column("alpha", sa.Numeric(10, 2)),
    sa.column("beta", sa.Numeric(10, 2)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    op.create_table(
        "factor_weights",
        sa.Column("factor_name", sa.String, primary_key=True),
        sa.Column("weight", sa.Numeric(5, 4), nullable=False),
        sa.Column("alpha", sa.Numeric(10, 2), nullable=False),
        sa.Column("beta", sa.Numeric(10, 2), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.bulk_insert(
        _factor_weights_table,
        [
            {
                "factor_name": name,
                "weight": weight,
                "alpha": round(weight * _PRIOR_STRENGTH, 2),
                "beta": round((1.0 - weight) * _PRIOR_STRENGTH, 2),
            }
            for name, weight in _SEED_WEIGHTS.items()
        ],
    )


def downgrade() -> None:
    op.drop_table("factor_weights")
