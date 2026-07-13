"""Add 10m/30m/2h/3h continuous aggregates + refresh policies for all six.

F3.3 (Multi-Timeframe Aggregation). candles_15m and candles_1h already
existed (migration 0001) but had no refresh policy — a code-review gap
(docs/assumptions.md #14): they'd stay empty forever since nothing ever
called refresh_continuous_aggregate. This migration adds the missing
10m/30m/2h/3h views AND a refresh policy for all six.

Convention note: migration 0001 is a one-time snapshot of
database/schema.sql as it stood at the end of Phase 2 and must not be
edited again now that it's been applied to a real database — from here on,
schema changes are incremental deltas in new numbered migrations, the
standard Alembic pattern. database/schema.sql is still hand-updated
alongside each migration so it keeps reflecting the current full desired
state for anyone reading it as a reference, but only 0001 executes it
verbatim; every later migration (including this one) carries its own DDL.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-13
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (view_name, bucket_interval, start_offset, end_offset, schedule_interval)
_NEW_AGGREGATES = [
    ("candles_10m", "10 minutes", "1 day", "10 minutes", "10 minutes"),
    ("candles_30m", "30 minutes", "2 days", "30 minutes", "30 minutes"),
    ("candles_2h", "2 hours", "5 days", "2 hours", "2 hours"),
    ("candles_3h", "3 hours", "7 days", "3 hours", "3 hours"),
]

# Existing views from 0001 that never got a refresh policy.
_EXISTING_AGGREGATES_NEEDING_POLICY = [
    ("candles_15m", "1 day", "15 minutes", "15 minutes"),
    ("candles_1h", "3 days", "1 hour", "1 hour"),
]


def _create_view_sql(view_name: str, bucket_interval: str) -> str:
    return f"""
    CREATE MATERIALIZED VIEW {view_name}
    WITH (timescaledb.continuous) AS
    SELECT symbol,
           time_bucket('{bucket_interval}', ts) AS bucket,
           first(open, ts)  AS open,
           max(high)        AS high,
           min(low)         AS low,
           last(close, ts)  AS close,
           sum(volume)      AS volume
    FROM candles
    WHERE timeframe = '5m'
    GROUP BY symbol, bucket
    WITH NO DATA;
    """


def upgrade() -> None:
    for view_name, bucket_interval, _start, _end, _schedule in _NEW_AGGREGATES:
        op.execute(_create_view_sql(view_name, bucket_interval))

    # add_continuous_aggregate_policy is a catalog insert, not an initial
    # materialization — unlike CREATE MATERIALIZED VIEW ... WITH DATA, it's
    # fine inside Alembic's transaction.
    for view_name, start_offset, end_offset, schedule_interval in _EXISTING_AGGREGATES_NEEDING_POLICY:
        op.execute(
            f"""
            SELECT add_continuous_aggregate_policy('{view_name}',
                start_offset => INTERVAL '{start_offset}',
                end_offset   => INTERVAL '{end_offset}',
                schedule_interval => INTERVAL '{schedule_interval}');
            """
        )

    for view_name, bucket_interval, start_offset, end_offset, schedule_interval in _NEW_AGGREGATES:
        op.execute(
            f"""
            SELECT add_continuous_aggregate_policy('{view_name}',
                start_offset => INTERVAL '{start_offset}',
                end_offset   => INTERVAL '{end_offset}',
                schedule_interval => INTERVAL '{schedule_interval}');
            """
        )


def downgrade() -> None:
    for view_name, _bucket, _start, _end, _schedule in _NEW_AGGREGATES:
        op.execute(f"DROP MATERIALIZED VIEW IF EXISTS {view_name} CASCADE;")
    for view_name, _start, _end, _schedule in _EXISTING_AGGREGATES_NEEDING_POLICY:
        op.execute(f"SELECT remove_continuous_aggregate_policy('{view_name}', if_exists => TRUE);")
