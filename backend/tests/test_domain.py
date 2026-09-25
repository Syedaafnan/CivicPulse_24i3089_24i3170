import pytest

from app.domain import TRANSITIONS, Status, allowed_transitions, can_transition


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (Status.OPEN, Status.IN_PROGRESS),
        (Status.OPEN, Status.REJECTED),
        (Status.IN_PROGRESS, Status.RESOLVED),
        (Status.IN_PROGRESS, Status.REJECTED),
    ],
)
def test_valid_transitions(current: Status, target: Status) -> None:
    assert can_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (Status.OPEN, Status.RESOLVED),
        (Status.OPEN, Status.OPEN),
        (Status.IN_PROGRESS, Status.OPEN),
        (Status.RESOLVED, Status.OPEN),
        (Status.RESOLVED, Status.IN_PROGRESS),
        (Status.REJECTED, Status.OPEN),
    ],
)
def test_invalid_transitions(current: Status, target: Status) -> None:
    assert not can_transition(current, target)


def test_terminal_states_have_no_exits() -> None:
    assert allowed_transitions(Status.RESOLVED) == []
    assert allowed_transitions(Status.REJECTED) == []


def test_table_covers_every_status() -> None:
    assert set(TRANSITIONS) == set(Status)
