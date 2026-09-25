# Engineering notes

Answers to the eight questions in Assignment §5.2, with references to this repository's own files
and lines. Two answers (5 and 8) require data this document can't invent on your behalf — they're
left as explicit TODOs with instructions for what to fill in and how.

## 1. Three things that differ between a laptop and a CI runner, and the exact line freezing each

1. **Language/runtime versions.** A laptop might have any Python/Node installed locally; both are
   frozen to an exact patch version by the Dockerfile `FROM` lines: `backend/Dockerfile:3,13`
   (`FROM python:3.12.8-slim-bookworm`) and `frontend/Dockerfile:3` (`FROM
   node:22.12.0-alpine3.20`). Since `ci.yml`, `compose.yaml`, and the k8s manifests all build from
   these same Dockerfiles, the runner and every deploy target get byte-identical toolchains.

2. **Network access to the real LLM provider.** A developer's laptop can reach Groq; a CI runner
   should not depend on that (rate limits, flakiness, cost, and non-determinism). This is frozen by
   `.github/workflows/ci.yml:68` and `:204`, which set `TRIAGE_PROVIDER: simulated` for the
   backend-test and integration jobs respectively — CI always exercises `SimulatedTriage`
   (`backend/app/providers/triage/simulated.py`), never a live network call.

3. **Whether the database/cache exist at all.** A laptop running `docker compose up` has
   long-lived Postgres/Redis containers with named volumes; a CI runner starts from nothing. This
   is frozen by the `integration` job in `ci.yml`, which runs `docker compose up -d` and explicitly
   waits on `/ready` before proceeding — the same readiness contract
   (`backend/app/routes/health.py`) that Kubernetes readiness probes use, so "is the environment
   actually up" is answered identically in both places rather than assumed.

## 2. Where this pipeline sits on the CI/CD maturity ladder, and what the next rung buys

This pipeline sits at roughly **"continuous delivery with automated deployment to a verification
environment, gated by tests and security scanning"** — every merge to `main` is built, scanned
(Trivy), SBOM'd, and automatically deployed to an ephemeral kind cluster with a smoke test and a
printed HPA snapshot (`cd.yml`), and nothing publishes or deploys without passing the equivalent of
the prior stage (`needs:` chains: test → build-push → deploy-k8s).

It stops short of **full continuous deployment to a persistent, real production environment with
progressive delivery** — the deploy target is a disposable kind cluster created inside the same CI
run, not a long-lived cluster that receives a canary or blue/green rollout of real user traffic.
The next rung would replace the ephemeral kind cluster with a real, persistent cluster and add
progressive delivery (e.g. Argo Rollouts / a GitOps controller reconciling from the repo — see the
GitOps bonus item), which buys the ability to catch a bad deploy against real traffic patterns
before it reaches every user, rather than only against a synthetic smoke test.

## 3. The exact line guaranteeing build-once-deploy-many, and what breaks without it

For the backend, the image built once in `cd.yml`'s `build-push` job is deployed by digest
(`cd.yml:121-122`, `BACKEND_REF`/`FRONTEND_REF` built from `needs.build-push.outputs.*-digest`) —
the same artifact, not a rebuild, reaches `overlays/prod` (`cd.yml:174`).

For the frontend specifically, the guarantee is `frontend/src/config.ts` reading
`window.__CIVICPULSE_CONFIG__` at runtime instead of `import.meta.env` at build time, combined with
`frontend/docker-entrypoint.d/40-runtime-config.sh` regenerating `config.js` from environment
variables on every container start (see [ADR 0002](adr/0002-frontend-runtime-config.md)).

Without either guarantee, the same source commit would need a separate image built per
environment (one baked for dev's backend URL, one for prod's), which is exactly the
environment-specific-image failure mode §2.1 of the assignment calls out explicitly.

## 4. What "correct" means for a probabilistic LLM component, and how CI stays deterministic

With `TRIAGE_PROVIDER=llm`, "correct" cannot mean "returns exactly this category for this input
every time" — the same complaint text can reasonably classify differently across model versions or
even across calls. What we hold constant instead is the **contract**, not the content:
`TriageResult` must always validate against the Pydantic schema (`backend/app/schemas.py`),
`summary` must always be ≤140 chars, `confidence` must always be in `[0, 1]`, and on any failure to
satisfy that contract the system must fall back to `RuleBasedTriage` and record
`triaged_by="rules:fallback"` rather than surface a 500. That is what's actually tested
(`backend/tests/test_llm_provider.py`, `test_api.py`'s
`test_provider_that_always_raises_still_returns_201_with_rules_fallback`).

CI stays deterministic by never exercising the real LLM at all: `TRIAGE_PROVIDER=simulated`
(`ci.yml:68,204`) swaps in `SimulatedTriage`, a seeded, hash-based, network-free fake
(`backend/app/providers/triage/simulated.py`) with configurable failure injection — so the tests
that prove "a provider that always raises still returns 201 with fallback" or "malformed JSON is
rejected safely" are testing the same contract the real LLM must satisfy, without depending on the
real LLM's non-determinism to reliably trigger those code paths on every run.

## 5. HPA lag: seconds between offered load rising and replicas rising

Measured on a real run: `load/k6-script.js` against the kind cluster's Ingress, with
`scripts/record-hpa.sh` sampling `kubectl get hpa` every 5s (raw data: `docs/evidence/hpa-run2.csv`,
chart: `docs/evidence/replicas-vs-load-chart.png`, VPA cross-check: `docs/evidence/vpa-recommendation.txt`).

k6's second stage (`load/k6-script.js`'s `{duration:"1m", target:60}`) starts the real ramp at
**t=30s** into the run (the first 30s stage only ramps 0→10 VUs, which never pushes CPU over
target). From the CSV:

- **t=30s** — offered load starts rising (k6 begins ramping 10→60 VUs)
- **t=42s** (+12s) — `desired_replicas` first increases (2→3) as `cpu_utilisation_pct` crosses the
  60% target (75%) — this 12s is metrics-server's scrape interval + the HPA controller's sync
  period both landing close together
- **t=59s** (+29s from load start) — `current_replicas` actually increases (2→3) — the ~17s gap
  behind `desired_replicas` changing is pod scheduling + container start (image was already
  `kind load`-ed, so no pull time) + passing `startupProbe`
- **t=86s** (+56s from load start) — `current_replicas` reaches `maxReplicas: 10` — full scale-out
  complete

So: **~12s to detect, ~29s to the first additional pod, ~56s to full capacity.** This lines up with
`scaleUp.stabilizationWindowSeconds: 0` (`k8s/base/hpa.yaml:23`) contributing nothing to the delay —
the lag is entirely metrics-server's scrape cadence, the controller's own sync period, and real pod
startup time, exactly as predicted before running this.

A second, unplanned finding from the same run: CPU utilization did **not** come back down to target
once maxed out — it held at 380–456%/60% for the entire 3-minute sustained-load stage even at 10/10
replicas (see the chart). Cross-checked against `docs/evidence/vpa-recommendation.txt`: VPA's real
`Target` recommendation for the backend container is **476m CPU**, against the **100m** actually
requested in `k8s/base/backend.yaml:89`. So `maxReplicas: 10` wasn't the bottleneck — the per-pod
CPU request was undersized by roughly 4-5x relative to real demand, meaning this workload needed
either a higher `maxReplicas` ceiling or (per the VPA recommendation) a larger request per pod, not
faster autoscaling.

Scale-down was not captured within the recording window: k6's ramp-down stage doesn't bring CPU
back under target until roughly t=344-360s, and `scaleDown.stabilizationWindowSeconds: 300`
(`k8s/base/hpa.yaml:19`) requires 5 continuous minutes below target before scaling in — so the
earliest a scale-down could have started was around t=650-660s, well past where recording stopped
(t=365s). That gap between "load actually dropped" and "cooldown window even starts counting" is
itself the point of that setting: scaling down slowly on purpose costs nothing under real traffic
patterns, but does mean a short dip in load will never trigger a scale-in at all.

**What would reduce the lag:** a shorter metrics-server scrape interval or HPA sync period would
shave a few seconds off the ~12s detection time, but the larger, more actionable lever here is
sizing `requests.cpu` correctly in the first place (per the VPA recommendation) — a workload that
needed 476m and was scaled based on a 100m request will always look far more "overloaded" than it
is, triggering aggressive scale-out sooner than a correctly-sized request would.

## 6. Why VPA runs in `Off` mode, and the failure mode of running it in `Auto` alongside the HPA

`k8s/base/vpa.yaml:14` sets `updateMode: "Off"` — recommend only, never evict or resize live pods.

The reason: our HPA (`k8s/base/hpa.yaml`) scales on CPU **utilization**, which is
`usage ÷ requests.cpu`. A VPA in `Auto` mode changes `requests.cpu` directly. That means both
controllers are reading and writing the same signal from opposite ends: if VPA raises a pod's CPU
request in response to sustained load, computed utilization for that pod *drops* (same usage,
bigger denominator) even though real load hasn't changed — which can make the HPA scale **in**
right when more replicas were actually needed, raising per-pod load again, which pushes VPA to
raise the request further, which drops computed utilization again. The two controllers chase each
other's output instead of converging. Recommender mode breaks this loop: VPA still computes and
publishes `Target`/`Lower Bound`/`Upper Bound` recommendations, but a human reads them and updates
the manifest's `resources.requests` deliberately, on their own schedule — decoupled from the HPA's
control loop entirely.

## 7. Where `internal: true` leaves the service that calls a hosted LLM, and how we resolved it

Compose's `internal: true` network (`compose.yaml:133`) has no route to the outside world, and
Postgres/Redis live on it exclusively (`compose.yaml:29,45` — `networks: [internal]`). The backend
is deliberately the **only** service on both networks (`compose.yaml:76`,
`networks: [edge, internal]`), which is what makes it possible for the backend to reach Postgres
and Redis *and* still reach Groq's public API over the internet — `internal: true` only blocks
egress for containers whose *only* network membership is `internal`, not for a container that also
holds a normal bridge-network membership.

The Kubernetes equivalent is `k8s/base/networkpolicy.yaml`, which achieves the same asymmetry the
opposite way: rather than denying egress from Postgres/Redis, it denies **ingress** to them from
anything except backend pods (`podSelector: matchLabels: { app: backend }`, lines 12-16 for
Postgres, mirrored for Redis) — Kubernetes NetworkPolicies are namespace-scoped and don't have a
Compose-style "no route to the outside world" primitive out of the box, so the resolution there is
to lock down who can reach the database/cache, while leaving the backend pod's own egress
unrestricted so it can still reach Groq.

## 8. The failure — something that cost more than an hour

**TODO — this one has to be a real incident from your own work on this project, not a generic
one.** Write 3-5 sentences covering:
- **Symptoms**: what you actually observed (an error message, a hung request, a wrong dashboard
  number, a CI job that wouldn't go green).
- **What you wrongly believed first**: your initial, incorrect theory about the cause, and why it
  seemed plausible at the time.
- **The exact command or log line that finally told you the truth**: paste it verbatim.

Good candidates to look back at, if nothing comes to mind immediately: the first time
`docker compose up` failed because of the `internal: true` network and a service couldn't resolve
another container's hostname; the first `kubectl rollout status` that hung because a readiness
probe was pointed at the wrong path; a coverage or lint failure in CI that passed locally but
failed in the runner because of the environment differences described in Q1; or a migration that
worked against a fresh database but failed against the seeded one.
