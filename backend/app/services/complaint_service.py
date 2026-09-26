"""Business rules for complaints: validate → triage → persist; the status state machine."""

from __future__ import annotations

import uuid

from app.domain import Status, can_transition
from app.models import Complaint
from app.repositories.complaint_repository import ComplaintFilters, ComplaintRepository
from app.schemas import ComplaintCreate
from app.services.errors import InvalidTransitionError, NotFoundError
from app.services.stats_service import StatsService
from app.services.triage_service import TriageService


class ComplaintService:
    def __init__(self, repo: ComplaintRepository, triage: TriageService, stats: StatsService) -> None:
        self._repo = repo
        self._triage = triage
        self._stats = stats

    def create(self, data: ComplaintCreate) -> Complaint:
        complaint_id = uuid.uuid4()  # server-generated, and known before triage so logs can cite it
        # Triage happens before any DB work, so a slow LLM never holds a transaction open.
        outcome = self._triage.triage(str(complaint_id), data.text, data.location)
        complaint = Complaint(
            id=complaint_id,
            text=data.text,
            location=data.location,
            reporter_contact=data.reporter_contact,
            category=outcome.result.category,
            priority=outcome.result.priority,
            status=Status.OPEN,
            ai_summary=outcome.result.summary,
            triaged_by=outcome.triaged_by,
            triage_latency_ms=outcome.latency_ms,
        )
        self._repo.add(complaint)
        self._repo.commit()
        self._stats.invalidate()  # after commit, so a concurrent reader can't re-cache stale numbers
        return complaint

    def get(self, complaint_id: uuid.UUID) -> Complaint:
        complaint = self._repo.get(complaint_id)
        if complaint is None:
            raise NotFoundError("complaint")
        return complaint

    def list(self, filters: ComplaintFilters, page: int, page_size: int) -> tuple[list[Complaint], int]:
        return self._repo.list(filters, page, page_size)

    def change_status(self, complaint_id: uuid.UUID, target: Status) -> Complaint:
        # Row lock so two operators can't both "advance" the same complaint concurrently.
        complaint = self._repo.get(complaint_id, for_update=True)
        if complaint is None:
            raise NotFoundError("complaint")
        current = Status(complaint.status)
        if not can_transition(current, target):
            self._repo.rollback()
            raise InvalidTransitionError(current, target)
        self._repo.set_status(complaint, target)
        self._repo.commit()
        self._stats.invalidate()
        return complaint
