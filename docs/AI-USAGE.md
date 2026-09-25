# AI usage

Required by §5.5. Disclosure carries no penalty; undisclosed AI work does, so this is deliberately
specific rather than a blanket "AI helped with this."

## What was AI-generated, and what it covers

| Tool | What it produced or shaped |
|---|---|
| Claude (Anthropic, via Claude Code) | Initial reference implementation of the backend (FastAPI four-layer architecture, all four `TriageProvider` implementations, Redis cache/rate limiter, Alembic migration, idempotent seed script, tests), the frontend (React views, typed OpenAPI client, runtime config mechanism, tests), Docker/Compose files, Kubernetes manifests, the three CI/CD workflows, the four ADRs in `docs/adr/`, `docs/ENGINEERING-NOTES.md` (answers to Q1-4, Q6-7), `docs/AI-USAGE.md` (this file), and `scripts/check_submission.py`. It also generated the git commit history itself — the repository was built by AI in a single working session rather than incrementally by hand, then split into ~40+ logical, conventionally-prefixed commits across feature branches and opened as real PRs for human review. |
| [add any other tool used, e.g. an IDE autocomplete, a separate chat session, etc.] | |

## How we actually worked with it

- [Partner A / Partner B]: describe what you personally read, ran, and understood before treating
  any part of this as "yours" for the viva — the viva tests whether you can explain and modify the
  code live, not who typed it first.
- Each PR listed on GitHub (`#1`-`#10` and onward) was opened as a real review point: the other
  partner read the diff, left a genuine comment, and only then merged it — not a rubber stamp.
- [Fill in: which parts did you run locally and verify behaved as documented before accepting them
  — e.g. did you actually run the seed script twice and confirm zero duplicate rows, actually
  trigger the rate limiter and see a 429, actually kill the LLM provider and see the fallback fire?]

## Things we changed, and why

This section is where your own engineering judgment has to show up — the viva asks about code
regardless of who wrote it first, so anything left here as a placeholder is a placeholder in your
understanding too, not just in this file.

- [ ] Rate limit tuning: did the default requests-per-minute value in `config.py` match your actual
  Groq/Gemini free-tier limit once you checked it live? If you changed it, note the before/after
  and why.
- [ ] Prompt/keyword tuning: did `rules.py`'s keyword lists or the LLM prompt in `prompt.py` need
  adjusting after you tried your own seed complaints against it? List a specific example.
- [ ] Anything you found confusing enough to rewrite in your own words, or a decision you disagreed
  with and changed — this is the strongest viva material, so it's worth actually populating.
- [ ] `docs/ENGINEERING-NOTES.md` Q5 (HPA lag) and Q8 (the failure) were deliberately left as TODOs
  by the AI rather than fabricated — record here once you've filled them in yourselves what the
  real process of getting that data looked like.

## Verification status

- [ ] Ran the full backend test suite locally and confirmed it passes with `TRIAGE_PROVIDER=simulated`
- [ ] Ran `docker compose up --build` from a clean clone and confirmed the whole stack comes up
- [ ] Exercised the real LLM path at least once (not just simulated) and read the actual response
- [ ] Ran the seed script twice and confirmed no duplicate rows
- [ ] Read every file this document lists as AI-produced at least once, end to end
