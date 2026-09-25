"""Aggregate statistics behind a Redis read-through cache.

Why TTL *and* explicit invalidation?
  * Invalidation on write makes a new complaint show up immediately.
  * The TTL is the safety net for writes that bypass this service (a manual
    SQL fix, a crashed pod between commit and delete, another service) —
    staleness is bounded to 30 s even when invalidation is missed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.domain import Category, Priority, Status
from app.providers.cache import JsonCache
from app.schemas import StatsOut

if TYPE_CHECKING:
    from app.repositories.complaint_repository import ComplaintRepository

STATS_KEY = "stats:v1"


class StatsService:
    def __init__(self, cache: JsonCache, ttl_seconds: int, repo: ComplaintRepository | None = None) -> None:
        self._cache = cache
        self._ttl = ttl_seconds
        self._repo = repo

    def get(self) -> tuple[StatsOut, bool]:
        """Returns (stats, cache_hit)."""
        cached = self._cache.get(STATS_KEY)
        if cached is not None:
            return StatsOut.model_validate(cached), True
        assert self._repo is not None
        agg = self._repo.aggregates()
        stats = StatsOut(
            total=agg.total,
            by_category={c: agg.by_category.get(c.value, 0) for c in Category},
            by_priority={p: agg.by_priority.get(p.value, 0) for p in Priority},
            by_status={s: agg.by_status.get(s.value, 0) for s in Status},
            by_triaged_by=agg.by_triaged_by,
            avg_triage_latency_ms=round(agg.avg_latency_ms, 1) if agg.avg_latency_ms is not None else None,
            generated_at=datetime.now(UTC),
        )
        self._cache.set(STATS_KEY, stats.model_dump(mode="json"), self._ttl)
        return stats, False

    def invalidate(self) -> None:
        self._cache.delete(STATS_KEY)
