"""Map domain errors and validation errors to the HTTP contract."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.services.errors import InvalidTransitionError, NotFoundError, RateLimitExceededError


def _field_name(loc: tuple[object, ...]) -> str:
    # ("body", "text") -> "text"; ("query", "page_size") -> "page_size"
    parts = [str(p) for p in loc if p not in ("body", "query", "path")]
    return ".".join(parts) or "body"


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"field": _field_name(tuple(e["loc"])), "message": str(e["msg"]).removeprefix("Value error, ")}
            for e in exc.errors()
        ]
        return JSONResponse({"detail": "Validation failed", "errors": errors}, status_code=400)

    @app.exception_handler(NotFoundError)
    async def not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(InvalidTransitionError)
    async def conflict(_: Request, exc: InvalidTransitionError) -> JSONResponse:
        return JSONResponse(
            {"detail": str(exc), "current": exc.current.value, "attempted": exc.attempted.value},
            status_code=409,
        )

    @app.exception_handler(RateLimitExceededError)
    async def rate_limited(_: Request, exc: RateLimitExceededError) -> JSONResponse:
        from app.metrics import RATE_LIMITED

        RATE_LIMITED.inc()
        return JSONResponse({"detail": str(exc)}, status_code=429, headers={"Retry-After": str(exc.retry_after)})
