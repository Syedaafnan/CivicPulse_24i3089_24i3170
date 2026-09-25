"""Triage orchestration: content-hash cache → primary provider → rules fallback.

A citizen never sees a 500 because a third party was slow, rate-limited or wrong.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from app.metrics import TRIAGE_CACHE, TRIAGE_FALLBACKS, TRIAGE_LATENCY
from app.providers.cache import JsonCache
from app.providers.triage.base import TriageProvider
from app.providers.triage.rules import RuleBasedTriage
from app.schemas import TriageResult

log = logging.getLogger(__name__)

CACHE_PREFIX = "triage:v1:"
HITS_KEY = "triage:cache:hits"
MISSES_KEY = "triage:cache:misses"
RECENT_KEY = "triage:recent"
RECENT_CAP = 20
FALLBACK_NAME = "rules:fallback"


@dataclass(frozen=True)
class TriageOutcome:
    result: TriageResult
    triaged_by: str
    latency_ms: int
    fallback: bool
    cached: bool
    error: str | None = None


def content_hash(text: str, location: str) -> str:
    """Normalised so trivially different duplicates ("Street 12 " vs "street 12") share one inference."""
    norm = " ".join(text.lower().split()) + "|" + " ".join(location.lower().split())
    return hashlib.sha256(norm.encode()).hexdigest()


class TriageService:
    def __init__(
        self,
        provider: TriageProvider,
        cache: JsonCache,
        cache_ttl_seconds: int,
        fallback: TriageProvider | None = None,
    ) -> None:
        self.provider = provider
        self.fallback = fallback or RuleBasedTriage()
        self._cache = cache
        self._ttl = cache_ttl_seconds

    def triage(self, complaint_id: str, text: str, location: str) -> TriageOutcome:
        started = time.perf_counter()
        key = CACHE_PREFIX + content_hash(text, location)

        cached = self._cache.get(key)
        if cached is not None:
            try:
                result = TriageResult.model_validate(cached["result"])
                outcome = TriageOutcome(result, cached["triaged_by"], self._ms(started), False, True)
                self._cache.incr(HITS_KEY)
                TRIAGE_CACHE.labels("hit").inc()
                return self._record(complaint_id, outcome)
            except (KeyError, ValueError):
                self._cache.delete(key)  # poisoned entry: drop it and re-triage
        self._cache.incr(MISSES_KEY)
        TRIAGE_CACHE.labels("miss").inc()

        try:
            result = self.provider.triage(text, location)
            outcome = TriageOutcome(result, self.provider.name, self._ms(started), False, False)
            # Only cache real answers. Caching a fallback would pin the rules result for 24 h.
            self._cache.set(
                key, {"result": result.model_dump(mode="json"), "triaged_by": self.provider.name}, self._ttl
            )
        except Exception as exc:  # noqa: BLE001 — any provider failure must degrade, not 500
            error = type(exc).__name__
            log.warning(
                "triage fallback",
                extra={"complaint_id": complaint_id, "provider": self.provider.name, "error_class": error},
            )
            TRIAGE_FALLBACKS.labels(self.provider.name, error).inc()
            result = self.fallback.triage(text, location)
            outcome = TriageOutcome(result, FALLBACK_NAME, self._ms(started), True, False, error)

        TRIAGE_LATENCY.labels(outcome.triaged_by).observe(outcome.latency_ms / 1000)
        return self._record(complaint_id, outcome)

    # -- observability -------------------------------------------------------
    def _record(self, complaint_id: str, outcome: TriageOutcome) -> TriageOutcome:
        self._cache.push_capped(
            RECENT_KEY,
            {
                "complaint_id": complaint_id,
                "provider": outcome.triaged_by,
                "latency_ms": outcome.latency_ms,
                "fallback": outcome.fallback,
                "cached": outcome.cached,
                "error": outcome.error,
                "at": datetime.now(UTC).isoformat(),
            },
            RECENT_CAP,
        )
        return outcome

    def recent(self) -> list[dict[str, object]]:
        return self._cache.list_recent(RECENT_KEY, RECENT_CAP)

    def cache_counts(self) -> tuple[int, int]:
        return self._cache.get_int(HITS_KEY), self._cache.get_int(MISSES_KEY)

    @staticmethod
    def _ms(started: float) -> int:
        return int((time.perf_counter() - started) * 1000)
