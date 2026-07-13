"""Tests for src/db/risk_settings.py (Phase 7 Pass 2b's VIX-threshold resolver)."""

import uuid
from unittest.mock import MagicMock

import pytest

from src.config import Settings
from src.db.founder import FOUNDER_EMAIL
from src.db.models import RiskSettings, User
from src.db.risk_settings import get_vix_thresholds


def _settings() -> Settings:
    return Settings(
        SECRET_KEY="s", DATABASE_URL="sqlite:///:memory:",
        VIX_NORMAL_MAX=15.0, VIX_ELEVATED_MAX=20.0, VIX_HIGH_MAX=30.0,
    )


def _founder() -> User:
    return User(id=uuid.uuid4(), email=FOUNDER_EMAIL, hashed_password="x")


def test_prefers_the_db_row_over_env_defaults():
    founder = _founder()
    row = RiskSettings(user_id=founder.id, vix_normal_max=10.0, vix_elevated_max=18.0, vix_high_max=25.0)
    db = MagicMock()
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: founder),
        MagicMock(scalar_one_or_none=lambda: row),
    ]

    thresholds = get_vix_thresholds(db, _settings())

    assert thresholds == (10.0, 18.0, 25.0)


def test_falls_back_to_env_defaults_when_no_row_exists():
    founder = _founder()
    db = MagicMock()
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: founder),
        MagicMock(scalar_one_or_none=lambda: None),
    ]

    thresholds = get_vix_thresholds(db, _settings())

    assert thresholds == (15.0, 20.0, 30.0)


def test_raises_when_founder_is_missing():
    db = MagicMock()
    db.execute.side_effect = [MagicMock(scalar_one_or_none=lambda: None)]

    with pytest.raises(RuntimeError, match="founder"):
        get_vix_thresholds(db, _settings())
