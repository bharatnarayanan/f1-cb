"""Redis wrapper for live-tick/quote caching and, later, rate limiting and
alert dedup (docs/CLAUDE.md section 4).

Phase 2 scope: a small get/set-with-TTL cache used to keep on-demand Kite
Connect quote lookups (docs/api_routes.md -> GET /market/quote/{symbol})
from hammering the upstream API and its rate limits. Rate limiting and
alert-dedup keys are later-phase concerns layered on top of this same
client, not built here.
"""

import json
from functools import lru_cache
from typing import Any

import redis

from src.config import get_settings

DEFAULT_QUOTE_TTL_SECONDS = 5


class RedisCache:
    def __init__(self, client: redis.Redis) -> None:
        self._client = client

    def get_json(self, key: str) -> Any | None:
        raw = self._client.get(key)
        return json.loads(raw) if raw is not None else None

    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        self._client.set(key, json.dumps(value), ex=ttl_seconds)

    def ping(self) -> bool:
        return bool(self._client.ping())


@lru_cache
def get_redis_cache() -> RedisCache:
    client = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
    return RedisCache(client)
