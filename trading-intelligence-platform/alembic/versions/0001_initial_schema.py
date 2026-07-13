"""Initial schema — applies database/schema.sql verbatim.

database/schema.sql is the canonical DDL (docs/CLAUDE.md section 7, kept in
sync by hand rather than duplicated into this file). `alembic upgrade head`
(run by the `api` service on every startup, docker-compose.yml) is now the
SOLE schema-creation path — there is no docker-entrypoint-initdb.d mount of
schema.sql anymore (see docs/assumptions.md #13), so a fresh Postgres volume
only ever gets tables via this migration.

upgrade() checks for an already-applied schema before running the DDL: a
`timescaledb_data` volume created by an older version of docker-compose.yml
(back when it DID mount schema.sql into docker-entrypoint-initdb.d) has all
the tables but no `alembic_version` row, so a naive re-run of the raw SQL
would fail on "relation already exists" and abort the api container's
startup (`pip install && alembic upgrade head && uvicorn ...` is
`&&`-chained). Detecting that case and skipping the DDL lets Alembic just
record the revision as applied instead.

Revision ID: 0001
Revises:
Create Date: 2026-07-08
"""

from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA_SQL_PATH = Path(__file__).resolve().parents[2] / "database" / "schema.sql"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "candles" in inspector.get_table_names():
        # Schema already exists (e.g. a volume from before docker-compose.yml
        # stopped auto-initializing via docker-entrypoint-initdb.d) — nothing
        # to do, just let Alembic stamp this revision as applied.
        return
    op.execute(_SCHEMA_SQL_PATH.read_text())


def downgrade() -> None:
    # Initial-schema baseline: full reset rather than reverse-engineering
    # per-table drops out of schema.sql. Fine for a personal MVP tool with
    # no other migrations layered on top yet (docs/CLAUDE.md section 5).
    op.execute("DROP SCHEMA public CASCADE")
    op.execute("CREATE SCHEMA public")
