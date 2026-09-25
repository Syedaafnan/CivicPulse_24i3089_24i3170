# ADR 0001: TriageProvider interface

## Status
Accepted

## Context
The core problem statement for CivicPulse is that the classifier reading a complaint must be
replaceable: a keyword rule today, a hosted LLM tomorrow, a fine-tuned model next year — and the
system must not care which, or fall over when the current one is slow, rate-limited, or wrong.

That means the rest of the backend (routes, services, persistence) cannot depend on any single
provider's request/response shape, error types, or failure modes.

## Decision
We defined a single `TriageProvider` protocol (`backend/app/providers/triage/base.py:15`) with one
method: `triage(self, text: str, location: str) -> TriageResult`. Two design choices follow
directly from the requirement above:

1. **The signature only accepts `text` and `location`.** `reporter_contact` is not a parameter of
   this interface at all — it is structurally impossible for any triage provider implementation to
   receive it, rather than relying on each provider to remember not to forward it. See
   [ADR 0004](0004-pii-and-data-governance.md) for why this matters.

2. **A shared, provider-agnostic error hierarchy** (`backend/app/providers/triage/base.py:21-45`):
   `TriageTimeout`, `TriageRateLimited`, `TriageUpstreamError` (all retryable — collected in
   `RETRYABLE` at line 45), plus `TriageBadRequest` and `TriageMalformedOutput` (never retried).
   Every provider implementation maps its own failure modes onto these five types, so
   `TriageService` (`backend/app/services/triage_service.py`) can implement retry/fallback logic
   once, against the interface, instead of once per provider.

The output side is constrained the same way: every provider must return a `TriageResult`
(`backend/app/schemas.py`) — `category`, `priority`, `summary` (≤140 chars), `confidence`
(0.0–1.0) — and `TriageService` re-validates that model regardless of what the provider claims to
have returned (see `backend/app/providers/triage/prompt.py`'s `parse_triage_json`, which is the
only place a raw LLM response is trusted, and even there it's parsed defensively).

Four implementations exist behind this interface, selected by the `TRIAGE_PROVIDER` env var via
`backend/app/providers/triage/factory.py`:

| Provider | File | Role |
|---|---|---|
| `LLMTriage` | `llm.py` | Production path — Groq, OpenAI-compatible, JSON mode |
| `OllamaTriage` | `ollama.py` | Offline path, no external network, no rate limit |
| `RuleBasedTriage` | `rules.py` | Deterministic fallback — always available, never fails |
| `SimulatedTriage` | `simulated.py` | Deterministic fake for CI — seeded, no network |

## Consequences
- Adding a fifth provider (e.g. a fine-tuned classifier) requires no change to routes, services, or
  the retry/fallback logic — only a new class implementing `triage()` and a factory branch.
- The retry-once-with-jitter policy (`llm.py:32-34`, `48`, `86-92`) and the fallback-to-rules
  behaviour live in exactly one place (`TriageService`), not duplicated per provider.
- The cost of this abstraction is that every new provider must correctly translate its own
  exceptions into the shared five-type hierarchy — a provider that raises something outside that
  hierarchy would bypass the retry/fallback logic entirely, so this mapping is unit-tested per
  provider (`backend/tests/test_llm_provider.py`, `test_rules_and_prompt.py`).
