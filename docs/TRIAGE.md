# Triage subsystem

How a complaint gets a category, priority, and summary — the design reference. For *why* it's
built this way, see [ADR 0001](adr/0001-provider-interface.md) and
[ADR 0004](adr/0004-pii-and-data-governance.md); this file is the *how*.

## Selecting a provider

`TRIAGE_PROVIDER` picks one of four implementations at startup
(`backend/app/providers/triage/factory.py`):

| Value | Class | Where it runs |
|---|---|---|
| `llm` (default in prod) | `LLMTriage` | Calls a hosted, OpenAI-compatible endpoint over HTTPS |
| `ollama` | `OllamaTriage` | Calls a container in the Compose stack, no external network |
| `rules` | `RuleBasedTriage` | In-process, no network, no external dependency at all |
| `simulated` | `SimulatedTriage` | In-process deterministic fake, used only in CI |

If `TRIAGE_PROVIDER=llm` but `LLM_API_KEY` isn't set, `factory.build_provider` catches the
resulting `ValueError` and falls back to `RuleBasedTriage` at startup (logged as a warning) rather
than failing to boot — a missing key degrades the system, it doesn't crash it.

## The LLM path

`LLMTriage` (`backend/app/providers/triage/llm.py`) targets any OpenAI-compatible chat-completions
endpoint. Configured via `config.py`:

- `LLM_BASE_URL` — defaults to `https://api.groq.com/openai/v1`
- `LLM_MODEL` — defaults to `llama-3.1-8b-instant` (a small, fast instruct model — classifying a
  paragraph doesn't need a large one, and Groq's speed matters when a citizen is watching a
  spinner)
- `LLM_PROVIDER_LABEL` — defaults to `groq`, recorded in `triaged_by` as `llm:groq`

Because the same `_HttpJsonProvider` base class backs both `LLMTriage` and `OllamaTriage`, pointing
`LLM_BASE_URL`/`LLM_MODEL` at a different OpenAI-compatible free tier (OpenRouter, Gemini's
OpenAI-compatible endpoint, etc.) requires no code change — see the assignment's list of
alternative free endpoints.

`OllamaTriage` (`ollama.py`) talks to `OLLAMA_BASE_URL` (default `http://ollama:11434`, the
Compose service name) running `OLLAMA_MODEL` (default `llama3.2:1b`) — no API key, no external
network, no rate limit, and no complaint text ever leaves the Compose network.

## Prompt design and the injection guardrail

Both HTTP-based providers build their request via `prompt.build_messages` (`prompt.py`), which:

1. Wraps the citizen's `text` and `location` in explicit `<complaint>`/`<location>` delimiter tags.
2. Strips any delimiter-like substrings the citizen typed, so a complaint body cannot forge a
   closing tag and inject its own instructions into the surrounding prompt.
3. Instructs the model explicitly to treat the delimited content as data, not instructions, and to
   respond only with the fields the schema expects.

Whatever the model actually replies with is still re-validated against the `TriageResult` Pydantic
schema before it's trusted (see `parse_triage_json` in `prompt.py`) — the guardrail is defence in
depth, not the only line of defence. `backend/tests/test_api.py`'s
`test_prompt_injection_cannot_choose_the_category` proves this end-to-end: even a fully "obedient"
compromised model that tries to return an out-of-enum category gets overridden by the
schema-validation/fallback path, not by the prompt wording alone.

## Resilience: timeout, retry, fallback

- Every HTTP call to `llm`/`ollama` carries a hard timeout (`TRIAGE_TIMEOUT_SECONDS`, capped at 10s
  in `config.py`).
- Exactly one retry, with jitter, and only for `TriageTimeout` / `TriageRateLimited` /
  `TriageUpstreamError` (`base.py`'s `RETRYABLE` tuple) — never for a 400 or a malformed-output
  error, since retrying those would just repeat the same failure.
- If the provider still fails after that retry, `TriageService`
  (`backend/app/services/triage_service.py`) falls back to `RuleBasedTriage` and records
  `triaged_by="rules:fallback"`. The citizen always gets a `201`, never a `500`, regardless of what
  the third-party provider is doing.

## Rule-based fallback

`RuleBasedTriage` (`rules.py`) matches the complaint text against per-category keyword lists that
include the Roman-Urdu terms citizens actually use ("pani", "bijli", "gutter", "kachra", "sarak",
etc. — the same vocabulary the seed data uses). It has no external dependency of any kind, so it is
the provider CivicPulse can always fall back to.

## Caching

Every successful triage result is cached in Redis by a SHA-256 hash of the normalized
`text`+`location`, for `TRIAGE_CACHE_TTL_SECONDS` (24h by default) — so nine neighbours reporting
the same burst main cost one inference, not nine. Fallback results are deliberately **not**
cached, so a temporary provider outage doesn't pin a low-confidence rules-based answer for a full
day once the provider recovers. Hit/miss counters back the cache-hit-rate figure surfaced at
`GET /api/meta/providers`.

## Observability

`GET /api/meta/providers` reports the currently active provider, all available provider names, the
measured cache hit rate, and the last 20 real triage outcomes (provider, latency in milliseconds,
whether it was a cache hit, whether it fell back) — this is the first place to look when triage
"feels" wrong or slow; see `docs/RUNBOOK.md` for the operational playbook.
