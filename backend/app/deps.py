"""FastAPI dependency wiring. Routes ask for *services*; they never see a session."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, Request

from app.container import Container
from app.repositories.complaint_repository import ComplaintRepository
from app.services.complaint_service import ComplaintService
from app.services.errors import RateLimitExceededError
from app.services.health_service import HealthService
from app.services.stats_service import StatsService
from app.services.triage_service import TriageService


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


def _repository(container: Container = Depends(get_container)) -> Iterator[ComplaintRepository]:
    with container.repository() as repo:
        yield repo


def get_stats_service(
    container: Container = Depends(get_container), repo: ComplaintRepository = Depends(_repository)
) -> StatsService:
    return StatsService(container.cache, container.settings.stats_cache_ttl_seconds, repo)


def get_complaint_service(
    container: Container = Depends(get_container),
    repo: ComplaintRepository = Depends(_repository),
) -> ComplaintService:
    stats = StatsService(container.cache, container.settings.stats_cache_ttl_seconds)
    return ComplaintService(repo, container.triage, stats)


def get_triage_service(container: Container = Depends(get_container)) -> TriageService:
    return container.triage


def get_health_service(container: Container = Depends(get_container)) -> HealthService:
    return HealthService(container.repository, container.cache)


def client_ip(request: Request, trust_proxy: bool) -> str:
    if trust_proxy:
        real = request.headers.get("x-real-ip")
        if real:
            return real.strip()
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request, container: Container = Depends(get_container)) -> None:
    ip = client_ip(request, container.settings.trust_proxy_headers)
    decision = container.rate_limiter.hit(ip)
    if not decision.allowed:
        raise RateLimitExceededError(decision.retry_after)
