# AI usage

Required by §5.5.

## What AI produced

| Tool | Used for |
|---|---|
| Claude (Anthropic, via Claude Code) | The initial implementation of the backend, frontend, Dockerfiles and Compose files, Kubernetes manifests, CI/CD workflows, ADRs and `scripts/check_submission.py`, split into feature-branch commits and merged through PRs. Later sessions included the final check against the assignment, the one-command Compose fix (#60), and the CI changes that run tests on the shipped runtimes and scan the pushed image digest (#61). |

## What we did ourselves

- Apart from the initial commit, every change went through a PR and was merged on GitHub.
- Q5's HPA numbers come from our own k6 run (`docs/evidence/hpa-run2.csv`).
- Q8 is our own incident: the `record-hpa.sh` crash, and our wrong first theory that metrics-server
  wasn't ready. Claude reproduced the `bash -x` trace quoted in the answer.

## Verified before submitting

- Backend tests pass (93% coverage), as do the frontend tests, lint, typecheck and build.
- A fresh clone starts with seeded data from `docker compose up --build` alone.
- A real LLM request was triaged by Groq (`triaged_by: llm:groq`). The rate limiter returns 429,
  and the stats cache returns `X-Cache: MISS` then `HIT`.
- The frontend can't reach Postgres, in either Compose or Kubernetes.
- In Kubernetes, the HPA reports live CPU usage, and `kubectl rollout undo` finished in 29.6 s.
