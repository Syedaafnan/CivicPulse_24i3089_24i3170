"""Process entrypoint with graceful SIGTERM handling.

On SIGTERM (Kubernetes rolling update, `docker compose stop`):
  1. mark the pod as draining → /ready returns 503, so it leaves Service endpoints;
  2. uvicorn stops accepting new connections and waits for in-flight requests
     (up to GRACEFUL_SHUTDOWN_SECONDS);
  3. the lifespan shutdown closes the DB pool and Redis client; the process exits 0.
"""

from __future__ import annotations

import logging
from types import FrameType

import uvicorn

from app.config import get_settings
from app.main import create_app

log = logging.getLogger("civicpulse.server")


class DrainingServer(uvicorn.Server):
    def handle_exit(self, sig: int, frame: FrameType | None) -> None:
        container = getattr(self.config.app.state, "container", None) if hasattr(self.config.app, "state") else None
        if container is not None and not container.draining:
            container.draining = True
            log.info("SIGTERM received: draining in-flight requests", extra={"signal": sig})
        super().handle_exit(sig, frame)


def main() -> None:
    settings = get_settings()
    app = create_app(settings)
    config = uvicorn.Config(
        app,
        host="0.0.0.0",  # noqa: S104 — container must listen on all interfaces
        port=settings.port,
        proxy_headers=True,
        forwarded_allow_ips="*",
        access_log=False,
        log_config=None,
        timeout_graceful_shutdown=settings.graceful_shutdown_seconds,
    )
    DrainingServer(config).run()


if __name__ == "__main__":
    main()
