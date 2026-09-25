"""RuleBasedTriage — deterministic keyword fallback. Always available, never fails.

Keywords include common Urdu/Roman-Urdu words citizens actually use
(e.g. "pani", "bijli", "gutter", "sarak").
"""

from __future__ import annotations

import re

from app.domain import SUMMARY_MAX, Category, Priority
from app.schemas import TriageResult

KEYWORDS: dict[Category, tuple[str, ...]] = {
    Category.WATER: (
        "water",
        "pipe",
        "burst",
        "leak",
        "flood",
        "tap",
        "supply",
        "pani",
        "tanker",
        "main line",
        "overflowing tank",
        "no water",
    ),
    Category.ELECTRICITY: (
        "electric",
        "electricity",
        "power",
        "outage",
        "load shedding",
        "loadshedding",
        "transformer",
        "wire",
        "bijli",
        "voltage",
        "meter",
        "shock",
        "sparking",
    ),
    Category.SANITATION: (
        "garbage",
        "trash",
        "waste",
        "sewage",
        "sewer",
        "gutter",
        "drain",
        "smell",
        "kachra",
        "overflow",
        "nala",
        "dump",
        "mosquito",
    ),
    Category.ROADS: (
        "road",
        "pothole",
        "sarak",
        "asphalt",
        "speed breaker",
        "footpath",
        "crack",
        "bridge",
        "construction",
        "traffic signal",
        "manhole",
    ),
    Category.STREETLIGHTS: (
        "streetlight",
        "street light",
        "street-light",
        "lamp",
        "pole light",
        "light pole",
        "dark street",
    ),
}

HIGH_WORDS = (
    "burst",
    "flood",
    "fire",
    "sparking",
    "shock",
    "live wire",
    "danger",
    "emergency",
    "urgent",
    "injur",
    "accident",
    "collapse",
    "child",
    "hospital",
    "since fajr",
    "since yesterday",
    "entering",
    "open manhole",
    "no water for",
    "3 days",
    "three days",
)
LOW_WORDS = ("suggestion", "request", "minor", "whenever possible", "cosmetic", "paint", "faded")

_WS = re.compile(r"\s+")


def _score(text: str, words: tuple[str, ...]) -> int:
    return sum(1 for w in words if w in text)


class RuleBasedTriage:
    name = "rules"

    def triage(self, text: str, location: str) -> TriageResult:
        lowered = text.lower()
        # Streetlights must win over generic "light"/"electric" words, so it is scored like the rest
        # and ties are broken by declaration order above.
        scores = {cat: _score(lowered, words) for cat, words in KEYWORDS.items()}
        best = max(scores, key=lambda c: scores[c])
        category = best if scores[best] > 0 else Category.OTHER

        if _score(lowered, HIGH_WORDS) > 0:
            priority = Priority.HIGH
        elif _score(lowered, LOW_WORDS) > 0:
            priority = Priority.LOW
        else:
            priority = Priority.NORMAL

        summary = _WS.sub(" ", text).strip()
        prefix = f"{category.value.capitalize()} issue at {location.strip()}: "
        full = prefix + summary
        if len(full) > SUMMARY_MAX:
            full = full[: SUMMARY_MAX - 1].rstrip() + "…"
        matched = scores[best]
        confidence = 0.3 if category is Category.OTHER else min(0.9, 0.5 + 0.1 * matched)
        return TriageResult(category=category, priority=priority, summary=full, confidence=confidence)
