"""All SQL lives here, and nowhere else."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.domain import Category, Priority, Status
from app.models import Complaint


@dataclass(frozen=True)
class ComplaintFilters:
    category: Category | None = None
    priority: Priority | None = None
    status: Status | None = None


@dataclass(frozen=True)
class Aggregates:
    total: int
    by_category: dict[str, int]
    by_priority: dict[str, int]
    by_status: dict[str, int]
    by_triaged_by: dict[str, int]
    avg_latency_ms: float | None


class ComplaintRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    # -- writes -------------------------------------------------------------
    def add(self, complaint: Complaint) -> Complaint:
        self._s.add(complaint)
        self._s.flush()
        return complaint

    def add_if_absent(self, complaint: Complaint) -> bool:
        """Insert unless a row with the same id exists. Used by the idempotent seed."""
        if self._s.get(Complaint, complaint.id) is not None:
            return False
        self._s.add(complaint)
        self._s.flush()
        return True

    def set_status(self, complaint: Complaint, status: Status) -> Complaint:
        complaint.status = status
        self._s.flush()
        return complaint

    def commit(self) -> None:
        self._s.commit()

    def rollback(self) -> None:
        self._s.rollback()

    # -- reads --------------------------------------------------------------
    def get(self, complaint_id: uuid.UUID, *, for_update: bool = False) -> Complaint | None:
        if for_update:
            stmt = select(Complaint).where(Complaint.id == complaint_id).with_for_update()
            return self._s.execute(stmt).scalar_one_or_none()
        return self._s.get(Complaint, complaint_id)

    def list(self, filters: ComplaintFilters, page: int, page_size: int) -> tuple[list[Complaint], int]:
        conditions = []
        if filters.category is not None:
            conditions.append(Complaint.category == filters.category)
        if filters.priority is not None:
            conditions.append(Complaint.priority == filters.priority)
        if filters.status is not None:
            conditions.append(Complaint.status == filters.status)

        total = self._s.execute(select(func.count()).select_from(Complaint).where(*conditions)).scalar_one()
        rows = (
            self._s.execute(
                select(Complaint)
                .where(*conditions)
                .order_by(Complaint.created_at.desc(), Complaint.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .scalars()
            .all()
        )
        return list(rows), int(total)

    def aggregates(self) -> Aggregates:
        def grouped(col: object) -> dict[str, int]:
            result = self._s.execute(select(col, func.count()).group_by(col)).all()  # type: ignore[call-overload]
            return {(k.value if hasattr(k, "value") else str(k)): int(v) for k, v in result}

        total, avg = self._s.execute(select(func.count(), func.avg(Complaint.triage_latency_ms))).one()
        return Aggregates(
            total=int(total),
            by_category=grouped(Complaint.category),
            by_priority=grouped(Complaint.priority),
            by_status=grouped(Complaint.status),
            by_triaged_by=grouped(Complaint.triaged_by),
            avg_latency_ms=float(avg) if avg is not None else None,
        )

    def lock_for_seed(self) -> None:
        """Transaction-scoped advisory lock (Postgres only) so concurrent seeders don't race."""
        if self._s.get_bind().dialect.name == "postgresql":
            self._s.execute(text("SELECT pg_advisory_xact_lock(727274002)"))

    def ping(self) -> None:
        """Readiness check. Raises if the database is unreachable."""
        self._s.execute(text("SELECT 1"))
