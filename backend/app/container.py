"""Composition root: builds long-lived collaborators once per process."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

import redis
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db import make_engine, make_session_factory
from app.providers.cache import JsonCache, RateLimiter
from app.providers.triage.base import TriageProvider
from app.providers.triage.factory import build_provider
from app.repositories.complaint_repository import ComplaintRepository
from app.services.triage_service import TriageService


@dataclass
class Container:
    settings: Settings
    engine: Engine
    session_factory: sessionmaker[Session]
    redis: redis.Redis
    cache: JsonCache
    rate_limiter: RateLimiter
    triage: TriageService
    draining: bool = field(default=False)

    @contextmanager
    def repository(self) -> Iterator[ComplaintRepository]:
        session = self.session_factory()
        try:
            yield ComplaintRepository(session)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def close(self) -> None:
        self.engine.dispose()
        self.redis.close()


def build_container(
    settings: Settings,
    *,
    engine: Engine | None = None,
    redis_client: redis.Redis | None = None,
    provider: TriageProvider | None = None,
) -> Container:
    engine = engine or make_engine(settings.database_url, settings.db_pool_size)
    r = redis_client or redis.Redis.from_url(settings.redis_url, socket_timeout=2, socket_connect_timeout=2)
    cache = JsonCache(r)
    return Container(
        settings=settings,
        engine=engine,
        session_factory=make_session_factory(engine),
        redis=r,
        cache=cache,
        rate_limiter=RateLimiter(r, settings.rate_limit_requests, settings.rate_limit_window_seconds),
        triage=TriageService(provider or build_provider(settings), cache, settings.triage_cache_ttl_seconds),
    )
