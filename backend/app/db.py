"""Engine and session factory. Only repositories use sessions."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def make_engine(url: str, pool_size: int = 5) -> Engine:
    kwargs: dict[str, object] = {"pool_pre_ping": True}
    if not url.startswith("sqlite"):
        kwargs.update(pool_size=pool_size, max_overflow=pool_size, pool_timeout=5)
    return create_engine(url, **kwargs)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
