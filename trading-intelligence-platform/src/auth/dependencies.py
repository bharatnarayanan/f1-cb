"""get_current_user — the FastAPI dependency every protected route adds.

auto_error=False on HTTPBearer so a missing Authorization header raises
our own AuthenticationError (-> 401 via src/main.py's handler) rather than
FastAPI's default 403 for a missing security scheme — one consistent
status/response shape for every kind of auth failure (missing header,
malformed token, expired token, unknown user).
"""

import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.exceptions import AuthenticationError
from src.auth.jwt import decode_access_token
from src.config import Settings, get_settings
from src.db.models import User
from src.db.session import get_db

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    if credentials is None:
        raise AuthenticationError("Missing Authorization header.")

    user_id = decode_access_token(credentials.credentials, settings)
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError as exc:
        raise AuthenticationError("Token subject is not a valid user id.") from exc

    user = db.execute(select(User).where(User.id == user_uuid)).scalar_one_or_none()
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or inactive.")
    return user
