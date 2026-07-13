"""The single founder user (Phase 5, migration 0004) — no login/auth system
exists yet (confirmed deliberate: see docs/assumptions.md #36), so every
route that needs a `created_by`/`user_id` FK resolves this one row instead.

Was duplicated identically in src/routes/strategies.py, journal.py, and
paper_trades.py; extracted here once Pass 2b needed a 4th call site
(src/db/risk_settings.py).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import User

FOUNDER_EMAIL = "founder@local"  # seeded by alembic/versions/0004_seed_founder_strategy.py


def get_founder(db: Session) -> User:
    founder = db.execute(select(User).where(User.email == FOUNDER_EMAIL)).scalar_one_or_none()
    if founder is None:
        raise RuntimeError(f"No founder user found (email={FOUNDER_EMAIL!r}) — check migration 0004 ran.")
    return founder
