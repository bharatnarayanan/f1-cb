"""Tests for src/worker/market_hours.py (Phase 8, worker service pass)."""

from datetime import datetime, timezone

from src.worker.market_hours import is_market_open


def _utc(y, m, d, h, mi):
    return datetime(y, m, d, h, mi, tzinfo=timezone.utc)


def test_open_during_regular_hours_on_a_weekday():
    # 2026-07-14 is a Tuesday. 10:00 IST == 04:30 UTC.
    assert is_market_open(_utc(2026, 7, 14, 4, 30)) is True


def test_open_at_the_exact_open_boundary():
    # 09:15 IST == 03:45 UTC.
    assert is_market_open(_utc(2026, 7, 14, 3, 45)) is True


def test_open_at_the_exact_close_boundary():
    # 15:30 IST == 10:00 UTC.
    assert is_market_open(_utc(2026, 7, 14, 10, 0)) is True


def test_closed_before_open():
    # 09:00 IST == 03:30 UTC.
    assert is_market_open(_utc(2026, 7, 14, 3, 30)) is False


def test_closed_after_close():
    # 15:31 IST == 10:01 UTC.
    assert is_market_open(_utc(2026, 7, 14, 10, 1)) is False


def test_closed_on_saturday():
    # 2026-07-18 is a Saturday, well within regular hours in IST.
    assert is_market_open(_utc(2026, 7, 18, 6, 0)) is False


def test_closed_on_sunday():
    # 2026-07-19 is a Sunday.
    assert is_market_open(_utc(2026, 7, 19, 6, 0)) is False
