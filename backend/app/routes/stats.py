from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.deps import get_stats_service
from app.schemas import StatsOut
from app.services.stats_service import StatsService

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats", response_model=StatsOut)
def get_stats(response: Response, svc: StatsService = Depends(get_stats_service)) -> StatsOut:
    stats, hit = svc.get()
    response.headers["X-Cache"] = "HIT" if hit else "MISS"
    response.headers["Cache-Control"] = "no-store"  # browsers must not hide our X-Cache behaviour
    return stats
