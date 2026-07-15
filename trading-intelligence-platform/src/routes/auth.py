"""Login route (docs/CLAUDE.md section 4: "Email/password, JWT, bcrypt").

Single founder, no signup route exists or ever should — see
docs/CLAUDE.md's non-goals ("Public multi-tenant SaaS: freemium tiers,
billing, public signup"). This validates a password against the one
seeded founder row (src/db/founder.py) and issues a JWT; it never creates
a user. The founder's password is set once via
scripts/set_founder_password.py, not through any HTTP route.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.exceptions import AuthenticationError
from src.auth.jwt import create_access_token
from src.auth.password import verify_password
from src.config import Settings, get_settings
from src.db.models import User
from src.db.session import get_db

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    user = db.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
    # Same error for "no such user" and "wrong password" — a real founder
    # deployment has exactly one email anyway, but this avoids the classic
    # user-enumeration tell regardless.
    if user is None or not user.is_active or not verify_password(body.password, user.hashed_password):
        raise AuthenticationError("Incorrect email or password.")

    token = create_access_token(str(user.id), settings)
    return LoginResponse(access_token=token)
