"""Liveness, readiness and metrics.

/health  → liveness. "Is the process alive?" Touches NOTHING external.
           A failing liveness probe restarts the pod, so a slow database must never fail it.
/ready   → readiness. 200 only if Postgres AND Redis answer; else 503 naming the failure.
           A failing readiness probe removes the pod from the Service (no restart).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.container import Container
from app.deps import get_container, get_health_service
from app.services.health_service import HealthService

router = APIRouter(tags=["ops"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", responses={503: {"description": "A dependency is unreachable or the pod is draining"}})
def ready(
    container: Container = Depends(get_container), svc: HealthService = Depends(get_health_service)
) -> JSONResponse:
    if container.draining:
        return JSONResponse({"status": "draining", "failed": []}, status_code=503)
    failed = svc.failed_dependencies()
    if failed:
        return JSONResponse({"status": "unready", "failed": failed}, status_code=503)
    return JSONResponse({"status": "ready", "failed": []})


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
