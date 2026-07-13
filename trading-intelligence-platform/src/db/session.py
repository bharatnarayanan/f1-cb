"""SQLAlchemy engine/session setup for TimescaleDB (Postgres 15 + extension).

database/schema.sql is the canonical DDL (see docs/CLAUDE.md section 7);
Alembic (alembic/versions/0001_initial_schema.py) applies that same file so
`alembic upgrade head` is the real deploy path, and docker-compose's
auto-init of a fresh volume is just a local-dev convenience mirroring it.

This module only defines the engine/session plumbing and the ORM models we
actually use in Phase 2 (AuditLog). Other tables stay schema-only until a
later phase's routes need an ORM model for them — see docs/assumptions.md.
"""

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.config import get_settings


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str):
    return create_engine(database_url, pool_pre_ping=True, future=True)


_engine = None
_SessionLocal: sessionmaker | None = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = build_engine(get_settings().database_url)
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: one session per request, always closed."""
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def check_db_connection(db: Session) -> bool:
    """Cheap liveness probe for /health — never used to gate a real query."""
    db.execute(text("SELECT 1"))
    return True
