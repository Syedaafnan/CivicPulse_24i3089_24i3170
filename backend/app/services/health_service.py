"""Readiness: are the dependencies this pod needs to serve traffic reachable?"""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager

from app.providers.cache import JsonCache
from app.repositories.complaint_repository import ComplaintRepository

log = logging.getLogger(__name__)


class HealthService:
    def __init__(self, repo_scope: Callable[[], AbstractContextManager[ComplaintRepository]], cache: JsonCache) -> None:
        self._repo_scope = repo_scope
        self._cache = cache

    def failed_dependencies(self) -> list[str]:
        failed: list[str] = []
        try:
            with self._repo_scope() as repo:
                repo.ping()
        except Exception as exc:  # noqa: BLE001
            log.warning("readiness: postgres unreachable", extra={"error": type(exc).__name__})
            failed.append("postgres")
        if not self._cache.ping():
            log.warning("readiness: redis unreachable")
            failed.append("redis")
        return failed
