"""HTTP only: parse, validate, serialise, status codes. No business rules, no sessions."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.deps import enforce_rate_limit, get_complaint_service
from app.domain import Category, Priority, Status, allowed_transitions
from app.models import Complaint
from app.repositories.complaint_repository import ComplaintFilters
from app.schemas import (
    ComplaintCreate,
    ComplaintOut,
    ComplaintPage,
    ErrorBody,
    StatusUpdate,
    TransitionErrorBody,
    ValidationErrorBody,
)
from app.services.complaint_service import ComplaintService

router = APIRouter(prefix="/api/complaints", tags=["complaints"])


def to_out(c: Complaint) -> ComplaintOut:
    return ComplaintOut.model_validate(
        {
            **{k: getattr(c, k) for k in ComplaintOut.model_fields if k != "allowed_transitions"},
            "allowed_transitions": allowed_transitions(Status(c.status)),
        }
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ComplaintOut,
    dependencies=[Depends(enforce_rate_limit)],
    responses={400: {"model": ValidationErrorBody}, 429: {"model": ErrorBody}},
)
def create_complaint(body: ComplaintCreate, svc: ComplaintService = Depends(get_complaint_service)) -> ComplaintOut:
    return to_out(svc.create(body))


@router.get("", response_model=ComplaintPage, responses={400: {"model": ValidationErrorBody}})
def list_complaints(
    category: Category | None = None,
    priority: Priority | None = None,
    status_: Status | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    svc: ComplaintService = Depends(get_complaint_service),
) -> ComplaintPage:
    items, total = svc.list(ComplaintFilters(category, priority, status_), page, page_size)
    return ComplaintPage(items=[to_out(c) for c in items], total=total, page=page, page_size=page_size)


@router.get("/{complaint_id}", response_model=ComplaintOut, responses={404: {"model": ErrorBody}})
def get_complaint(complaint_id: uuid.UUID, svc: ComplaintService = Depends(get_complaint_service)) -> ComplaintOut:
    return to_out(svc.get(complaint_id))


@router.patch(
    "/{complaint_id}/status",
    response_model=ComplaintOut,
    responses={404: {"model": ErrorBody}, 409: {"model": TransitionErrorBody}, 400: {"model": ValidationErrorBody}},
)
def change_status(
    complaint_id: uuid.UUID, body: StatusUpdate, svc: ComplaintService = Depends(get_complaint_service)
) -> ComplaintOut:
    return to_out(svc.change_status(complaint_id, body.status))
