"""Tests for src/config.py's Settings — specifically data_mode validation."""

import pytest
from pydantic import ValidationError

from src.config import Settings


def _base_kwargs() -> dict:
    return {
        "SECRET_KEY": "test-secret",
        "DATABASE_URL": "sqlite:///:memory:",
    }


def test_data_mode_defaults_to_sample():
    settings = Settings(**_base_kwargs())

    assert settings.data_mode == "sample"


def test_data_mode_accepts_live():
    settings = Settings(**_base_kwargs(), DATA_MODE="live")

    assert settings.data_mode == "live"


def test_data_mode_rejects_an_invalid_value():
    # Must fail loudly at startup rather than silently falling through to
    # the live-Kite branch in src/market_data/factory.py on a typo.
    with pytest.raises(ValidationError):
        Settings(**_base_kwargs(), DATA_MODE="Sample")
