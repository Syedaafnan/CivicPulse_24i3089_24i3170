# CivicPulse

[![ci](https://github.com/OWNER/civicpulse/actions/workflows/ci.yml/badge.svg?branch=dev)](https://github.com/OWNER/civicpulse/actions/workflows/ci.yml)
[![cd](https://github.com/OWNER/civicpulse/actions/workflows/cd.yml/badge.svg)](https://github.com/OWNER/civicpulse/actions/workflows/cd.yml)
<!-- replace OWNER with your GitHub user/org -->

Municipal complaint intake, AI triage and operations dashboard.

A citizen describes a problem in free text ("burst water main flooding Street 12 since fajr").
CivicPulse validates it, triages it into a **category**, a **priority** and a **one-line summary**
(with an LLM, falling back to keyword rules when the LLM is slow, rate-limited or wrong),
stores it in PostgreSQL, and shows it on a live operations dashboard with cached statistics.

> Still to write: the four ADRs, `docs/ENGINEERING-NOTES.md` (§5.2) and the evidence in `docs/evidence/`.

## Architecture

```mermaid
flowchart TB
  user([Citizen / Operator]) -->|HTTP :8080| fe
  subgraph edge [docker network: edge]
    fe[frontend<br/>React + Vite → nginx<br/>proxies /api]
    be[backend<br/>FastAPI + Pydantic]
  end
  subgraph internal [docker network: internal · internal: true]
    pg[(postgres:16<br/>volume pgdata)]
    rd[(redis:7<br/>cache + rate limiter)]
  end
  fe -->|/api| be
  be --> pg
  be --> rd
  be --> tp{{TriageProvider}}
  tp -->|default| llm[LLMTriage · Groq JSON mode]
  tp -->|offline| ol[OllamaTriage]
  tp -->|CI| sim[SimulatedTriage]
  llm -. timeout / 429 / bad JSON .-> rules[RuleBasedTriage · fallback]
```

## Quickstart

```bash
git clone <this repo> && cd civicpulse
cp .env.example .env          # optionally add a free Groq key and set TRIAGE_PROVIDER=llm
docker compose up --build     # migrations + seed run automatically
open http://localhost:8080
```

API docs (dev): http://localhost:8000/docs

### On Kubernetes (the second command)

```bash
./scripts/kind-up.sh          # kind cluster + ingress-nginx + metrics-server + images + k8s/overlays/dev
echo "127.0.0.1 civicpulse.local" | sudo tee -a /etc/hosts
open http://civicpulse.local
```

Production-style Compose with the CI-built images: `IMAGE_TAG=<sha> GHCR_OWNER=<owner> docker compose -f compose.prod.yaml up -d`.

### Without Docker (for development)

```bash
# backend (needs a local Postgres and Redis)
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+psycopg://civicpulse:civicpulse@127.0.0.1:5432/civicpulse REDIS_URL=redis://127.0.0.1:6379/0
alembic upgrade head && python -m app.seed && python -m app.server
pytest                        # 55 tests, SQLite + fakeredis, no network

# frontend
cd frontend && npm ci && npm run dev      # http://localhost:5173, proxies /api to :8000
npm test && npm run lint && npm run typecheck
```

## API

| Method | Path | Behaviour |
|---|---|---|
| POST | `/api/complaints` | Validate → triage → persist. **201**; **400** with field-level errors; **429** + `Retry-After` |
| GET | `/api/complaints/{id}` | 200 / 404 |
| GET | `/api/complaints` | Filter `category`, `priority`, `status`; paginate `page`, `page_size ≤ 100`; returns `total` |
| PATCH | `/api/complaints/{id}/status` | State machine; invalid transition → **409** naming the transition |
| GET | `/api/stats` | Aggregates, Redis-cached 30 s, `X-Cache: HIT\|MISS`, invalidated on write |
| GET | `/api/meta/providers` | Active provider, triage-cache hit rate, last 20 triage outcomes |
| GET | `/api/meta/enums` | Categories / priorities / statuses for UI filters |
| GET | `/health` | Liveness — never touches the database |
| GET | `/ready` | Readiness — 200 only if Postgres and Redis answer; 503 names the failure |
| GET | `/metrics` | Prometheus: request count, latency histogram, triage latency, fallback counter |

Status machine: `open → in_progress → resolved`, `open → rejected`, `in_progress → rejected`. `resolved`/`rejected` are terminal.

## Triage providers (`TRIAGE_PROVIDER`)

| Value | Class | Use |
|---|---|---|
| `llm` | `LLMTriage` | Groq (OpenAI-compatible) JSON mode, 10 s timeout, one jittered retry on timeout/429/5xx |
| `ollama` | `OllamaTriage` | Local model in Compose (`--profile ollama`) |
| `rules` | `RuleBasedTriage` | Deterministic keywords; also the fallback (`triaged_by = rules:fallback`) |
| `simulated` | `SimulatedTriage` | Deterministic fake for CI, with `SIMULATED_FAILURE_MODE=raise\|malformed\|timeout` |

## CI/CD

| Workflow | Trigger | Jobs |
|---|---|---|
| `ci.yml` | PR → `main`/`dev`, push → `dev` | lint-and-type · test-backend · test-frontend · build (no push) · scan (Trivy) · manifests (kubeconform) · integration (Compose smoke, network isolation, persistence) |
| `cd.yml` | push → `main` | test (full CI again) → build-push (GHCR `:<sha>`, SBOM, cosign) → deploy-k8s (kind, deploy **by digest**, rollout status, Ingress smoke, `kubectl get hpa`) |
| `release.yml` | tag `v*.*.*` | test → push semver tags + sign → GitHub Release with notes and digests |

All actions are pinned to commit SHAs. Every workflow has a least-privilege `permissions:` block. Credentials come from
`GITHUB_TOKEN` (GHCR) and repository secrets `POSTGRES_PASSWORD` / `LLM_API_KEY` (both optional for the ephemeral cluster).
Operations: [docs/RUNBOOK.md](docs/RUNBOOK.md) · scaling evidence: [docs/SCALING.md](docs/SCALING.md).

## Repository layout

```
backend/   app/{routes,services,repositories,providers}  alembic/  tests/  Dockerfile
frontend/  src/{components,pages,api}  tests/  Dockerfile  nginx.conf  default.conf.template
k8s/       base/{namespace,configmap,secret,postgres,redis,backend,frontend,ingress,hpa,vpa,pdb,networkpolicy}.yaml
           overlays/{dev,prod}/kustomization.yaml  kind-config.yaml
load/      k6-script.js
scripts/   kind-up.sh  cluster-addons.sh  smoke.sh  record-hpa.sh
.github/   workflows/{ci,cd,release}.yml  dependabot.yml
docs/      RUNBOOK.md  SCALING.md  GIT-WORKFLOW.md  AI-USAGE.md  screenshots/
compose.yaml  compose.prod.yaml  .env.example
```

## Screenshots

| Submit | Dashboard (server 409 shown verbatim) | Stats (X-Cache) |
|---|---|---|
| ![](docs/screenshots/ui-submit.png) | ![](docs/screenshots/ui-dashboard-409.png) | ![](docs/screenshots/ui-stats.png) |
