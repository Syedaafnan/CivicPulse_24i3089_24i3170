"""Pydantic models for the HTTP contract and for LLM output.

The same validation machinery guards both doors: untrusted citizen input
and untrusted model output.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain import (
    CONTACT_MAX,
    LOCATION_MAX,
    LOCATION_MIN,
    SUMMARY_MAX,
    TEXT_MAX,
    TEXT_MIN,
    Category,
    Priority,
    Status,
)

# ---------------------------------------------------------------- triage


class TriageResult(BaseModel):
    """What every TriageProvider must return. Extra keys from a model are rejected."""

    model_config = ConfigDict(extra="forbid")

    category: Category
    priority: Priority
    summary: str = Field(max_length=SUMMARY_MAX)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("summary")
    @classmethod
    def one_line(cls, v: str) -> str:
        v = v.strip()
        if "\n" in v or "\r" in v:
            raise ValueError("summary must be a single line")
        if not v:
            raise ValueError("summary must not be empty")
        return v


# ---------------------------------------------------------------- requests


class ComplaintCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    text: str = Field(
        min_length=TEXT_MIN, max_length=TEXT_MAX, examples=["Burst water main flooding Street 12 since fajr"]
    )
    location: str = Field(min_length=LOCATION_MIN, max_length=LOCATION_MAX, examples=["G-11/3, Street 12"])
    reporter_contact: str | None = Field(default=None, max_length=CONTACT_MAX)

    @field_validator("reporter_contact")
    @classmethod
    def blank_to_none(cls, v: str | None) -> str | None:
        return v or None


class StatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Status


# ---------------------------------------------------------------- responses


class ComplaintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    text: str
    location: str
    reporter_contact: str | None
    category: Category
    priority: Priority
    status: Status
    ai_summary: str | None
    triaged_by: str
    triage_latency_ms: int
    created_at: datetime
    updated_at: datetime
    allowed_transitions: list[Status] = Field(
        description="Statuses this complaint may move to next, decided by the server's state machine."
    )


class ComplaintPage(BaseModel):
    items: list[ComplaintOut]
    total: int
    page: int
    page_size: int


class FieldError(BaseModel):
    field: str
    message: str


class ValidationErrorBody(BaseModel):
    detail: str = "Validation failed"
    errors: list[FieldError]


class ErrorBody(BaseModel):
    detail: str


class TransitionErrorBody(BaseModel):
    detail: str
    current: Status
    attempted: Status


class StatsOut(BaseModel):
    total: int
    by_category: dict[Category, int]
    by_priority: dict[Priority, int]
    by_status: dict[Status, int]
    by_triaged_by: dict[str, int]
    avg_triage_latency_ms: float | None
    generated_at: datetime


class TriageOutcome(BaseModel):
    complaint_id: str
    provider: str
    latency_ms: int
    fallback: bool
    cached: bool
    error: str | None = None
    at: datetime


class ProvidersOut(BaseModel):
    active: str
    fallback: str
    available: list[str]
    cache_hits: int
    cache_misses: int
    cache_hit_rate: float | None
    recent: list[TriageOutcome]


class EnumsOut(BaseModel):
    categories: list[Category]
    priorities: list[Priority]
    statuses: list[Status]
