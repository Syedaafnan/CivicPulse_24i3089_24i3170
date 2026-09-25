"""The TriageProvider interface and the error taxonomy around it.

Everything above this interface (services, routes) is indifferent to
whether the reader is a keyword rule, a hosted LLM or a local model.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.schemas import TriageResult


@runtime_checkable
class TriageProvider(Protocol):
    name: str

    def triage(self, text: str, location: str) -> TriageResult: ...


class TriageError(Exception):
    """Base class: any failure that should trigger the rules fallback."""


class TriageTimeout(TriageError):
    """The provider did not answer inside the hard timeout. Retryable."""


class TriageRateLimited(TriageError):
    """HTTP 429 from the provider. Retryable."""


class TriageUpstreamError(TriageError):
    """HTTP 5xx or a transport failure. Retryable."""


class TriageBadRequest(TriageError):
    """HTTP 4xx other than 429 — our request was wrong and will be wrong again. NOT retryable."""


class TriageMalformedOutput(TriageError):
    """The model answered, but not with something our schema accepts. NOT retryable."""


RETRYABLE: tuple[type[TriageError], ...] = (TriageTimeout, TriageRateLimited, TriageUpstreamError)
