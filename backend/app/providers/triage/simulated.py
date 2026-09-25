"""SimulatedTriage — deterministic fake for CI. Seeded, no network, configurable failure injection.

The "answer" is derived from a hash of the input, so the same complaint always
gets the same result on every run and on every machine.
"""

from __future__ import annotations

import hashlib

from app.domain import Category
from app.providers.triage.base import TriageTimeout, TriageUpstreamError
from app.providers.triage.prompt import parse_triage_json
from app.providers.triage.rules import RuleBasedTriage
from app.schemas import TriageResult


class SimulatedTriage:
    name = "simulated"

    def __init__(self, failure_mode: str = "none", seed: str = "civicpulse") -> None:
        self._failure_mode = failure_mode
        self._seed = seed
        self._rules = RuleBasedTriage()

    def triage(self, text: str, location: str) -> TriageResult:
        if self._failure_mode == "raise":
            raise TriageUpstreamError("simulated upstream failure")
        if self._failure_mode == "timeout":
            raise TriageTimeout("simulated timeout")
        if self._failure_mode == "malformed":
            # Exercise the real validator with a plausible-but-wrong answer.
            return parse_triage_json('{"category": "potholes", "priority": "urgent", "summary": "x", "confidence": 2}')

        # Deterministic: rules decide category/priority (so results are sensible in demos),
        # the seeded hash decides confidence.
        base = self._rules.triage(text, location)
        digest = hashlib.sha256(f"{self._seed}|{text}|{location}".encode()).digest()
        confidence = round(0.6 + (digest[0] / 255) * 0.35, 2)
        if base.category is Category.OTHER:
            confidence = round(confidence / 2, 2)
        return base.model_copy(update={"confidence": confidence})
