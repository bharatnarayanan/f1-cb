"""Tests for src/worker/dedup.py (Phase 8, worker service pass)."""

from datetime import datetime, timezone

import fakeredis

from src.cache.redis_client import RedisCache
from src.worker.dedup import already_scanned, mark_scanned


def _cache() -> RedisCache:
    return RedisCache(fakeredis.FakeRedis(decode_responses=True))


def test_not_scanned_before_marking():
    cache = _cache()
    bar_ts = datetime(2026, 7, 14, 10, 0, tzinfo=timezone.utc)

    assert already_scanned(cache, "NSE:RELIANCE", "15m", bar_ts) is False


def test_scanned_after_marking():
    cache = _cache()
    bar_ts = datetime(2026, 7, 14, 10, 0, tzinfo=timezone.utc)

    mark_scanned(cache, "NSE:RELIANCE", "15m", bar_ts)

    assert already_scanned(cache, "NSE:RELIANCE", "15m", bar_ts) is True


def test_a_newer_bar_is_not_considered_already_scanned():
    cache = _cache()
    old_bar_ts = datetime(2026, 7, 14, 10, 0, tzinfo=timezone.utc)
    new_bar_ts = datetime(2026, 7, 14, 10, 15, tzinfo=timezone.utc)

    mark_scanned(cache, "NSE:RELIANCE", "15m", old_bar_ts)

    assert already_scanned(cache, "NSE:RELIANCE", "15m", new_bar_ts) is False


def test_dedup_keys_are_independent_per_symbol_and_timeframe():
    cache = _cache()
    bar_ts = datetime(2026, 7, 14, 10, 0, tzinfo=timezone.utc)

    mark_scanned(cache, "NSE:RELIANCE", "15m", bar_ts)

    assert already_scanned(cache, "NSE:INFY", "15m", bar_ts) is False
    assert already_scanned(cache, "NSE:RELIANCE", "30m", bar_ts) is False
