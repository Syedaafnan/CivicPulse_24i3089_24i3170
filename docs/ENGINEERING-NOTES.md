# Engineering notes

Answers to the eight questions in Assignment §5.2, with references to this repository's own files
and lines.

## 1. Three things that differ between a laptop and a CI runner, and the exact line freezing each

1. **Operating system and line endings.** Our laptops run Windows 11 with Git's `core.autocrlf`, and
   the runner is `ubuntu-24.04`. A shell script checked out with CRLF endings breaks inside a Linux
   container (`set: Illegal option -` from the stray `\r`). `.gitattributes:3`
   (`* text=auto eol=lf`) and `.gitattributes:5` (`*.sh text eol=lf`) freeze the line endings for
   every checkout on every OS. The Linux userland itself comes from the `FROM` lines below.

2. **Interpreter and runtime versions.** One laptop has Python 3.14 installed at `C:\Python314`, and
   Node is whatever version the developer installed last. What ships is frozen to an exact patch
   release by `backend/Dockerfile:3` and `:14` (`FROM python:3.14.7-slim-bookworm`, used by both
   the builder and runtime stages), `frontend/Dockerfile:3` (`FROM node:24.1.0-alpine3.20`) and
   `frontend/Dockerfile:11` (`FROM nginx:1.31.0-alpine`). `ci.yml`'s `build` job, `compose.yaml` and
   the Kubernetes manifests all use these same Dockerfiles, so the runner and every deploy target get
   the same toolchain. One gap remains: the lint and unit-test jobs run on the runner itself, not in
   a container, and use `ci.yml:17-18` (`PYTHON_VERSION: "3.12"`, `NODE_VERSION: "22"`). Those jobs
   therefore test on older versions than the ones we ship. The `integration` job closes most of that
   gap because it runs the image that was actually built.

3. **Dependency versions.** A laptop's `node_modules` or virtualenv drifts: packages get added by
   hand, or installs are left half-finished. During the final check, a local `frontend/node_modules`
   was missing `vitest`, `eslint` and `vite` entirely. In the image, `frontend/Dockerfile:5-6`
   copies `package-lock.json` and runs `npm ci`, which installs exactly what the lockfile lists and
   fails if the lockfile and `package.json` disagree. `backend/Dockerfile:9-10` installs
   `requirements.txt`, where every package except `starlette>=1.3.1` is pinned with `==`.

## 2. Where this pipeline sits on the CI/CD maturity ladder, and what the next rung buys

This pipeline sits at roughly **"continuous delivery with automated deployment to a verification
environment, gated by tests and security scanning"** — every merge to `main` is built, scanned
(Trivy), SBOM'd, and automatically deployed to an ephemeral kind cluster with a smoke test and a
printed HPA snapshot (`cd.yml`). Both images are signed keylessly with cosign (`cd.yml:99-100`), and
the signatures are verified again before anything is deployed (`cd.yml:133`). Nothing publishes or
deploys unless the stage before it has passed: `needs:` chains test → build-push → deploy-k8s at
`cd.yml:28` and `cd.yml:114`.

It stops short of **full continuous deployment to a persistent, real production environment with
progressive delivery** — the deploy target is a disposable kind cluster created inside the same CI
run, not a long-lived cluster that receives a canary or blue/green rollout of real user traffic.
The next rung would replace the ephemeral kind cluster with a real, persistent cluster and add
progressive delivery (e.g. Argo Rollouts / a GitOps controller reconciling from the repo — see the
GitOps bonus item), which buys the ability to catch a bad deploy against real traffic patterns
before it reaches every user, rather than only against a synthetic smoke test.

## 3. The exact line guaranteeing build-once-deploy-many, and what breaks without it

The line is `.github/workflows/cd.yml:174`:

```
kustomize edit set image "civicpulse-backend=$BACKEND_REF" "civicpulse-frontend=$FRONTEND_REF"
```

`$BACKEND_REF` and `$FRONTEND_REF` (`cd.yml:121-122`) are `ghcr.io/...@sha256:<digest>` values taken
from the `build-push` job's outputs (`cd.yml:36-37`). The deploy job never builds anything. It pins
the prod overlay to the exact bytes that were built, signed (`cd.yml:99-100`) and verified
(`cd.yml:133`). `cd.yml:176` then refuses to apply any rendered manifest that still contains
`:latest` or a placeholder image.

Build-once only works if the image contains nothing environment-specific. For the frontend,
`frontend/src/config.ts` reads `window.__CIVICPULSE_CONFIG__` at runtime rather than
`import.meta.env` at build time, and `frontend/docker-entrypoint.d/40-runtime-config.sh` writes
`config.js` from environment variables each time the container starts
([ADR 0002](adr/0002-frontend-runtime-config.md)).

**What breaks without it:** each environment would rebuild from source. The prod image would then be
a different artifact from the one that was tested, and a changed base image or dependency could slip
in between the two builds. The cosign check at `cd.yml:133` would also fail, or would verify an
image nobody tested. Deploying `:latest` instead of a digest has a similar problem: a later push can
move the tag while a rollout is still running, and a rollback can redeploy the very version it was
meant to undo ([ADR 0003](adr/0003-deploy-by-sha.md)).

**Known gap:** the Trivy scan in `ci.yml`'s `scan` job runs against the image CI built. `build-push`
then builds the image again from the same GHA layer cache. The two are almost certainly
byte-identical, but the pipeline doesn't prove it. The fix is to push once and then scan and sign
that one digest.

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

**Symptoms.** For the first HPA recording we started `scripts/record-hpa.sh` in the background and
then ran k6. The load test ran to completion and the HPA scaled out, but the CSV contained only its
header row. The script had exited after its first loop iteration without printing any error. That
run was lost, which is why the evidence file is `docs/evidence/hpa-run2.csv`.

**What we wrongly believed first.** We assumed metrics-server wasn't reporting yet. Right after a
deploy, `kubectl get hpa` shows `<unknown>/60%` for up to a minute, so we believed the `kubectl`
call inside the script was failing and killing it under `set -e`. We waited for real CPU numbers in
`kubectl get hpa` and re-ran the script, but it died the same way. That ruled out metrics-server:
`kubectl` was succeeding and returning data every time.

**What finally told us the truth.** Running the script with a trace:

```
$ bash -x scripts/record-hpa.sh hpa.csv; echo "exit status: $?"
+ read -r cur des cpu
++ kubectl -n civicpulse get hpa backend-hpa -o 'jsonpath={.status.currentReplicas} {.status.desiredReplicas} {.status.currentMetrics[0].resource.current.averageUtilization}'
exit status: 1
```

The last traced command is `read`, not `kubectl`, and `echo` never runs. Piping the same
`kubectl ... -o jsonpath=...` through `od -c` showed why: jsonpath output has no trailing newline.
When `read` hits end-of-file before a newline, it still fills the variables but returns 1, and
`set -e` (`scripts/record-hpa.sh:5`) treats that as fatal. The fix (commit `8515dce`) appends
`{"\n"}` to the jsonpath (`scripts/record-hpa.sh:12`) and adds `|| echo "0 0 0"` so that a
transient `kubectl` error records a zero row instead of killing the recorder. The lesson: when
`set -e` kills a script without a message, `bash -x` shows which command actually failed. The
failure may not be in the command you suspect.
