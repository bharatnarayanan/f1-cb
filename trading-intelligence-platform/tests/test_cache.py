"""Tests for src/cache/redis_client.py.

Unit tests run against fakeredis (no real Redis needed). The integration
test additionally proves the wrapper works against a real Redis instance —
skipped automatically if one isn't reachable (see docker-compose's `redis`
service, or `docker compose up -d redis`).
"""

import fakeredis
import pytest
import redis as redis_lib

from src.cache.redis_client import RedisCache


@pytest.fixture
def cache() -> RedisCache:
    return RedisCache(fakeredis.FakeRedis(decode_responses=True))


def test_get_json_returns_none_when_missing(cache: RedisCache):
    assert cache.get_json("nope") is None


def test_set_then_get_json_round_trips(cache: RedisCache):
    cache.set_json("quote:NSE:NIFTY 50", {"last_price": 24500.1}, ttl_seconds=5)

    assert cache.get_json("quote:NSE:NIFTY 50") == {"last_price": 24500.1}


def test_set_json_applies_ttl(cache: RedisCache):
    cache.set_json("k", {"v": 1}, ttl_seconds=5)

    ttl = cache._client.ttl("k")
    assert 0 < ttl <= 5


def test_ping():
    cache = RedisCache(fakeredis.FakeRedis())
    assert cache.ping() is True


def _real_redis_reachable() -> bool:
    try:
        redis_lib.Redis.from_url("redis://localhost:6379/0").ping()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _real_redis_reachable(), reason="no local Redis reachable on 6379")
def test_round_trip_against_real_redis():
    client = redis_lib.Redis.from_url("redis://localhost:6379/0", decode_responses=True)
    cache = RedisCache(client)

    cache.set_json("tip:test:phase2", {"ok": True}, ttl_seconds=5)
    try:
        assert cache.get_json("tip:test:phase2") == {"ok": True}
    finally:
        client.delete("tip:test:phase2")
