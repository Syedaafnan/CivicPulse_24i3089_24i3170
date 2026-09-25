"""Domain vocabulary and rules that do not depend on HTTP, SQL or any provider.

The status state machine lives here as an explicit transition table.
The frontend never copies this table: every complaint returned by the API
carries `allowed_transitions`, computed from this one source of truth.
"""

from __future__ import annotations

from enum import StrEnum


class Category(StrEnum):
    WATER = "water"
    ELECTRICITY = "electricity"
    SANITATION = "sanitation"
    ROADS = "roads"
    STREETLIGHTS = "streetlights"
    OTHER = "other"


class Priority(StrEnum):
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class Status(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    REJECTED = "rejected"


# The whole state machine. Anything not listed here is a 409.
TRANSITIONS: dict[Status, frozenset[Status]] = {
    Status.OPEN: frozenset({Status.IN_PROGRESS, Status.REJECTED}),
    Status.IN_PROGRESS: frozenset({Status.RESOLVED, Status.REJECTED}),
    Status.RESOLVED: frozenset(),  # terminal
    Status.REJECTED: frozenset(),  # terminal
}


def allowed_transitions(current: Status) -> list[Status]:
    """Stable, ordered list of statuses reachable from `current`."""
    order = list(Status)
    return sorted(TRANSITIONS[current], key=order.index)


def can_transition(current: Status, target: Status) -> bool:
    return target in TRANSITIONS[current]


# Text limits — enforced by Pydantic (HTTP), by CHECK constraints (DB),
# and mirrored (not replaced) by the frontend form.
TEXT_MIN, TEXT_MAX = 10, 2000
LOCATION_MIN, LOCATION_MAX = 3, 200
CONTACT_MAX = 200
SUMMARY_MAX = 140
