"""Observability surface: which triage provider is active and how it has been behaving."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_triage_service
from app.domain import Category, Priority, Status
from app.providers.triage.factory import AVAILABLE
from app.schemas import EnumsOut, ProvidersOut, TriageOutcome
from app.services.triage_service import FALLBACK_NAME, TriageService

router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("/providers", response_model=ProvidersOut)
def providers(svc: TriageService = Depends(get_triage_service)) -> ProvidersOut:
    hits, misses = svc.cache_counts()
    lookups = hits + misses
    return ProvidersOut(
        active=svc.provider.name,
        fallback=FALLBACK_NAME,
        available=AVAILABLE,
        cache_hits=hits,
        cache_misses=misses,
        cache_hit_rate=round(hits / lookups, 3) if lookups else None,
        recent=[TriageOutcome.model_validate(r) for r in svc.recent()],
    )


@router.get("/enums", response_model=EnumsOut)
def enums() -> EnumsOut:
    """Vocabulary for UI filters, so the frontend never hard-codes domain values."""
    return EnumsOut(categories=list(Category), priorities=list(Priority), statuses=list(Status))
