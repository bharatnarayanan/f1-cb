"""One-time founder password setup (Phase 8+ auth pass).

migration 0004 seeded the founder user's `hashed_password` with a random
placeholder (bcrypt.hashpw(uuid.uuid4().bytes, ...)) — nobody knows that
value, by design, since no login system existed yet. This script is how
you set a real password before POST /api/v1/auth/login can ever work.

Deliberately a local script, not an HTTP endpoint — an unauthenticated
"set password" route would itself be a hole. Needs the `src` package and
its DB dependencies (psycopg, SQLAlchemy) importable, which the api/worker
image already has — run it inside that container, not on the bare host:

  docker compose exec api python3 scripts/set_founder_password.py

Never logs or prints the password itself.
"""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.auth.password import hash_password  # noqa: E402
from src.db.founder import get_founder  # noqa: E402
from src.db.session import get_session_factory  # noqa: E402


def main() -> None:
    password = getpass.getpass("New founder password: ")
    if len(password) < 8:
        sys.exit("Password must be at least 8 characters.")
    confirm = getpass.getpass("Confirm: ")
    if password != confirm:
        sys.exit("Passwords didn't match — nothing changed.")

    db = get_session_factory()()
    try:
        founder = get_founder(db)
        founder.hashed_password = hash_password(password)
        db.commit()
    finally:
        db.close()

    print("Founder password updated. You can now POST /api/v1/auth/login.")


if __name__ == "__main__":
    main()
