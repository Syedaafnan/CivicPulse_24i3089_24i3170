"""SQLAlchemy ORM model. The schema itself is owned by Alembic migrations;
this module only maps it. Nothing calls `create_all` in application code."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, Index, Integer, String, Text, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain import Category, Priority, Status


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


def _enum(cls: type, name: str) -> Enum:
    return Enum(cls, name=name, values_callable=lambda e: [m.value for m in e], validate_strings=True)


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    reporter_contact: Mapped[str | None] = mapped_column(String(200), nullable=True)
    category: Mapped[Category] = mapped_column(_enum(Category, "complaint_category"), nullable=False)
    priority: Mapped[Priority] = mapped_column(_enum(Priority, "complaint_priority"), nullable=False)
    status: Mapped[Status] = mapped_column(
        _enum(Status, "complaint_status"), nullable=False, default=Status.OPEN, server_default=Status.OPEN.value
    )
    ai_summary: Mapped[str | None] = mapped_column(String(140), nullable=True)
    triaged_by: Mapped[str] = mapped_column(String(32), nullable=False)
    triage_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("length(text) BETWEEN 10 AND 2000", name="ck_complaints_text_len"),
        CheckConstraint("length(location) BETWEEN 3 AND 200", name="ck_complaints_location_len"),
        CheckConstraint("triage_latency_ms >= 0", name="ck_complaints_latency_nonneg"),
        # Dashboard filter: WHERE status = ? AND priority = ? ORDER BY created_at DESC
        Index("ix_complaints_status_priority", "status", "priority"),
        # Default dashboard listing: ORDER BY created_at DESC LIMIT/OFFSET
        Index("ix_complaints_created_at", "created_at"),
    )
