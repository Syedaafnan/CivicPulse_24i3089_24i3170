"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.container import Container, build_container
from app.errors import register_error_handlers
from app.logging_setup import configure_logging
from app.middleware import RequestContextMiddleware
from app.routes import complaints, health, meta, stats

log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        c = container or build_container(settings)
        app.state.container = c
        log.info("startup", extra={"triage_provider": c.triage.provider.name, "environment": settings.environment})
        yield
        # Runs after uvicorn has stopped accepting connections and drained in-flight requests.
        log.info("shutdown: closing connection pools")
        c.close()

    app = FastAPI(
        title="CivicPulse API",
        version="1.0.0",
        description="Municipal complaint intake, AI triage and operations.",
        lifespan=lifespan,
    )
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_methods=["GET", "POST", "PATCH"],
            allow_headers=["Content-Type", "X-Request-ID"],
            expose_headers=["X-Cache", "X-Request-ID", "Retry-After"],
        )
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)
    for r in (complaints.router, stats.router, meta.router, health.router):
        app.include_router(r)
    return app
