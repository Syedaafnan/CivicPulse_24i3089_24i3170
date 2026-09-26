"""Domain errors raised by services; exception handlers map them to HTTP status codes."""

from __future__ import annotations

from app.domain import Status, allowed_transitions


class NotFoundError(Exception):
    def __init__(self, what: str) -> None:
        super().__init__(f"{what} not found")


class InvalidTransitionError(Exception):
    def __init__(self, current: Status, attempted: Status) -> None:
        self.current = current
        self.attempted = attempted
        nxt = ", ".join(s.value for s in allowed_transitions(current)) or "nothing (terminal state)"
        super().__init__(
            f"Invalid status transition: {current.value} → {attempted.value}. '{current.value}' can move to: {nxt}."
        )


class RateLimitExceededError(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(f"Too many complaints from this address. Try again in {retry_after} s.")
