# ADR 0004: PII and data governance for hosted LLM calls

## Status
Accepted

## Context
A complaint's `text` and `location` fields are the two inputs the triage step needs to classify a
complaint. Citizens routinely also provide `reporter_contact` (name, phone number, address) as a
separate field, and complaint free-text itself can incidentally contain names or landmarks that
identify a person.

Once `TRIAGE_PROVIDER=llm` is selected, that data leaves the machine and reaches a third-party
hosted API (Groq by default; Gemini is a documented alternative — see §2.5 of the assignment
brief). Free tiers of hosted LLM providers vary in whether submitted content is retained or used
to improve the underlying model, and those terms change over time — the assignment brief itself
flags Gemini's free tier as an example where inputs may be used for model improvement. Whatever
provider is configured, the terms in effect on the day of submission should be checked against the
provider's current published policy rather than assumed from this document, since they can change.

## Decision
We resolved this at the interface level, not with a runtime redaction step that could be forgotten
or bypassed:

1. **`reporter_contact` is never passed to any `TriageProvider`.** The protocol's `triage()` method
   (`backend/app/providers/triage/base.py:15-18`) only accepts `text` and `location` as
   parameters — there is no code path by which the contact field can reach an LLM call, because
   the interface doesn't expose a parameter for it. This is a structural guarantee, not a policy
   one: adding a new provider that "forgets" to redact contact info is not possible, because it was
   never given the field to forward.

2. **Complaint `text` and `location` are still sent to the hosted provider**, and may contain
   incidental PII a citizen chose to include (a name, a landmark, a phone number typed into the
   free-text body itself). We accept this exposure rather than attempting automated PII scrubbing
   of free text, because:
   - Automated redaction (regex/NER-based) has a real false-negative rate, and a missed phone
     number is worse than an honestly-disclosed policy.
   - The complaint text is short (10–2000 chars, enforced at `backend/app/models.py`) and
     municipal in nature — the operational value of accurate classification outweighs the marginal
     PII risk versus the cost of building and maintaining a redaction layer for a portfolio system.
   - `RuleBasedTriage` and `SimulatedTriage` (the CI and network-degraded paths) never send
     anything anywhere, and `OllamaTriage` keeps the same complaint text fully on-machine — so an
     operator or team concerned about this exposure has a same-interface, zero-exposure fallback
     available via a one-line env var change, not a code change.

3. **The API key itself is never logged.** `LLMTriage` keeps the key as a private, name-mangled
   attribute excluded from `repr()`/logging (`llm.py`), sourced only from environment variables /
   Kubernetes Secrets / GitHub Secrets, never committed to the repository.

## Consequences
- If this project is ever adapted for a jurisdiction with stricter PII handling requirements (e.g.
  requiring on-premise-only processing of citizen-submitted text), the correct lever is switching
  `TRIAGE_PROVIDER` to `ollama` or `rules` — no application code changes.
- The team is responsible for re-verifying the active provider's current data-retention terms
  before each real submission/demo, since these terms are provider-controlled and can change
  independently of this document.
- We explicitly did **not** implement free-text PII redaction. If a future requirement demands it,
  it should be added as a transformation the caller applies before invoking `triage()`, not inside
  individual providers, to preserve the single-point-of-control property described in
  [ADR 0001](0001-provider-interface.md).
