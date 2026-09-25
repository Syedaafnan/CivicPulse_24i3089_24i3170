"""Pure-ASGI middleware: request id propagation, JSON access log, Prometheus metrics.

Pure ASGI (not BaseHTTPMiddleware) so the request_id contextvar is visible in
every log line emitted while the request is handled, including in threadpool code.
"""

from __future__ import annotations

import logging
import re
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.logging_setup import request_id_var
from app.metrics import HTTP_LATENCY, HTTP_REQUESTS

log = logging.getLogger("civicpulse.access")
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _route_template(scope: Scope) -> str:
    route = scope.get("route")
    path = getattr(route, "path", None)
    return path or "unmatched"  # never the raw path: unbounded label cardinality


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope["headers"]).get(b"x-request-id", b"").decode("latin-1")
        request_id = incoming if _SAFE_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message.setdefault("headers", [])
                message["headers"].append((b"x-request-id", request_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed = time.perf_counter() - started
            path = _route_template(scope)
            method = scope["method"]
            HTTP_REQUESTS.labels(method, path, str(status_code)).inc()
            HTTP_LATENCY.labels(method, path).observe(elapsed)
            if path not in ("/health", "/ready", "/metrics"):
                log.info(
                    "request",
                    extra={
                        "method": method,
                        "path": scope["path"],
                        "status": status_code,
                        "duration_ms": round(elapsed * 1000, 1),
                    },
                )
            request_id_var.reset(token)
