"""Password hashing/verification (docs/CLAUDE.md section 3: bcrypt-hashed,
never stored or logged in plaintext). Thin wrapper so every call site uses
the same encoding convention rather than each hand-rolling
.encode("utf-8")/.decode("ascii").
"""

import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("ascii"))
