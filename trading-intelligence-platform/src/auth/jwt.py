"""JWT issuance/validation (docs/CLAUDE.md section 4: "Email/password,
JWT, bcrypt"). Single-founder, single-device MVP — no refresh-token
rotation, just one access token with a long-ish expiry (see
src/config.py's access_token_expire_minutes).
"""

from datetime import datetime, timedelta, timezone

import jwt

from src.auth.exceptions import AuthenticationError
from src.config import Settings

_SUBJECT_CLAIM = "sub"


def create_access_token(user_id: str, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        _SUBJECT_CLAIM: user_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> str:
    """Returns the user_id claim. Raises AuthenticationError for any
    invalid/expired/malformed token — callers never need to know PyJWT's
    own exception hierarchy.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Token has expired — log in again.") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Invalid token.") from exc

    user_id = payload.get(_SUBJECT_CLAIM)
    if not user_id:
        raise AuthenticationError("Token is missing its subject claim.")
    return user_id
