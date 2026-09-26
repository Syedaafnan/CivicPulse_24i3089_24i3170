"""Test fixtures: SQLite in-memory + fakeredis + an injectable triage provider.

No network, no sleeps, no real LLM: every run is deterministic.
(Tests create the schema from the ORM metadata; the application itself never does —
production schema is owned by Alembic.)
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.container import Container, build_container
from app.main import create_app
from app.models import Base
from app.providers.triage.base import TriageProvider
from app.providers.triage.simulated import SimulatedTriage


class AlwaysRaises:
    name = "llm:broken"

    def __init__(self) -> None:
        self.calls = 0

    def triage(self, text: str, location: str):  # noqa: ANN201
        self.calls += 1
        raise RuntimeError("provider exploded")


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="sqlite://",
        redis_url="redis://unused",
        triage_provider="simulated",
        rate_limit_requests=5,
        rate_limit_window_seconds=60,
        log_level="WARNING",
    )


@pytest.fixture
def make_container(settings: Settings) -> Iterator[Callable[..., Container]]:
    engines = []

    def _make(provider: TriageProvider | None = None, **overrides: object) -> Container:
        s = settings.model_copy(update=overrides)
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        engines.append(engine)
        return build_container(
            s,
            engine=engine,
            redis_client=fakeredis.FakeRedis(),
            provider=provider or SimulatedTriage(),
        )

    yield _make
    for e in engines:
        e.dispose()


@pytest.fixture
def container(make_container: Callable[..., Container]) -> Container:
    return make_container()


@pytest.fixture
def client_for(settings: Settings) -> Callable[[Container], TestClient]:
    def _client(c: Container) -> TestClient:
        return TestClient(create_app(c.settings, container=c))

    return _client


@pytest.fixture
def client(container: Container, client_for: Callable[[Container], TestClient]) -> Iterator[TestClient]:
    with client_for(container) as tc:
        yield tc


VALID = {"text": "Burst water main flooding Street 12 since fajr", "location": "G-11/3 Street 12"}
