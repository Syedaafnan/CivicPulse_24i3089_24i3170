"""Redis doing two jobs, behind small interfaces:

  Job 1 — JsonCache: read-through cache (stats, 30 s) and triage content-hash cache (24 h).
  Job 2 — RateLimiter: distributed fixed-window counter shared by every backend replica.

Both fail OPEN: if Redis is down, requests are served uncached / unlimited and
/ready reports the outage. A cache outage must not become a citizen-facing 500.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, cast

import redis

log = logging.getLogger(__name__)


class JsonCache:
    def __init__(self, client: redis.Redis) -> None:
        self._r = client

    def get(self, key: str) -> Any | None:
        try:
            raw = cast(bytes | None, self._r.get(key))
        except redis.RedisError as exc:
            log.warning("cache get failed", extra={"key": key, "error": type(exc).__name__})
            return None
        return None if raw is None else json.loads(raw)

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        try:
            self._r.set(key, json.dumps(value, default=str), ex=ttl_seconds)
        except redis.RedisError as exc:
            log.warning("cache set failed", extra={"key": key, "error": type(exc).__name__})

    def delete(self, *keys: str) -> None:
        try:
            self._r.delete(*keys)
        except redis.RedisError as exc:
            log.warning("cache delete failed", extra={"keys": keys, "error": type(exc).__name__})

    def incr(self, key: str) -> None:
        try:
            self._r.incr(key)
        except redis.RedisError:
            pass

    def get_int(self, key: str) -> int:
        try:
            return int(cast(bytes | None, self._r.get(key)) or 0)
        except (redis.RedisError, ValueError):
            return 0

    def push_capped(self, key: str, value: Any, cap: int) -> None:
        try:
            pipe = self._r.pipeline()
            pipe.lpush(key, json.dumps(value, default=str))
            pipe.ltrim(key, 0, cap - 1)
            pipe.execute()
        except redis.RedisError:
            pass

    def list_recent(self, key: str, cap: int) -> list[Any]:
        try:
            return [json.loads(x) for x in cast(list[bytes], self._r.lrange(key, 0, cap - 1))]
        except redis.RedisError:
            return []

    def ping(self) -> bool:
        try:
            return bool(self._r.ping())
        except redis.RedisError:
            return False


@dataclass(frozen=True)
class RateDecision:
    allowed: bool
    remaining: int
    retry_after: int


class RateLimiter:
    """Fixed-window counter: INCR ratelimit:{ip}:{window}; first hit sets the expiry."""

    def __init__(self, client: redis.Redis, limit: int, window_seconds: int) -> None:
        self._r = client
        self.limit = limit
        self.window = window_seconds

    def hit(self, identity: str, now: float | None = None) -> RateDecision:
        now = time.time() if now is None else now
        window_start = int(now // self.window) * self.window
        key = f"ratelimit:{identity}:{window_start}"
        try:
            pipe = self._r.pipeline()
            pipe.incr(key)
            pipe.expire(key, self.window + 1)
            count, _ = pipe.execute()
        except redis.RedisError as exc:
            log.warning("rate limiter unavailable, failing open", extra={"error": type(exc).__name__})
            return RateDecision(True, self.limit, 0)
        retry_after = max(1, int(window_start + self.window - now + 0.999))
        if int(count) > self.limit:
            return RateDecision(False, 0, retry_after)
        return RateDecision(True, self.limit - int(count), retry_after)
