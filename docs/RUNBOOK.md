# CivicPulse runbook

Namespace for everything: `civicpulse`. Shorthand used below: `k="kubectl -n civicpulse"`.

## 1. Deploy

| Where | How |
|---|---|
| Laptop, Compose (dev) | `cp .env.example .env && docker compose up --build` → http://localhost:8080 |
| Laptop, Compose (prod images) | `IMAGE_TAG=<sha> GHCR_OWNER=<owner> docker compose -f compose.prod.yaml up -d` |
| Laptop, Kubernetes | `./scripts/kind-up.sh` → http://civicpulse.local (add `127.0.0.1 civicpulse.local` to `/etc/hosts`) |
| CI/CD | Merge a `dev → main` PR. `cd.yml` tests, pushes to GHCR, signs, and deploys **by digest** to an ephemeral kind cluster, then smoke-tests the Ingress |

**What is production running?**
```bash
$k get deploy backend -o jsonpath='{.spec.template.spec.containers[0].image}'
# ghcr.io/<owner>/civicpulse-backend@sha256:…  → the same digest as tag :<commit-sha> in GHCR
```
The CD run's summary and the `rendered-manifests-<sha>` artifact record exactly what was applied.

## 2. Roll back

### A. Fast and imperative: the 3 a.m. answer
```bash
$k rollout undo deployment/backend          # back to the previous ReplicaSet (revisionHistoryLimit: 5)
$k rollout undo deployment/frontend
$k rollout status deployment/backend
$k rollout history deployment/backend       # see what you can go back to; --to-revision=N for older
```
Takes seconds and needs no pipeline. **Downside:** the cluster now disagrees with Git, and the next `apply` puts the bad version straight back. Use it to stop the bleeding, then do B.

### B. Declarative and auditable: once the fire is out
Re-apply the prod overlay pinned to the previous good commit:
```bash
GOOD=<previous good commit sha>             # from git log / the last green cd.yml run
cd k8s/overlays/prod
kustomize edit set image \
  civicpulse-backend=ghcr.io/<owner>/civicpulse-backend:$GOOD \
  civicpulse-frontend=ghcr.io/<owner>/civicpulse-frontend:$GOOD
kustomize build . | kubectl apply -f -
git checkout kustomization.yaml             # don't commit the pin; Git history already has the SHA
```
Or, the fully-in-Git way: `git revert <bad merge commit>` on `dev`, PR to `main`, and let `cd.yml` deploy it.
**When:** always, after A, or on its own when there's no urgency. It's reviewable, and Git stays the source of truth.

## 3. Read logs

Every line is JSON on stdout with a `request_id` (echoed as the `X-Request-ID` response header).

```bash
$k logs deploy/backend -f                                   # one pod
$k logs -l app=backend --all-containers --prefix -f         # all backend pods (+ init container)
$k logs -l app=backend --tail=500 | jq -c 'select(.level=="WARNING")'
$k logs -l app=backend --tail=2000 | jq -c 'select(.request_id=="<id from X-Request-ID>")'
$k logs deploy/backend -c migrate                           # migrations + seed output
docker compose logs -f backend                              # Compose
```

## 4. When triage starts failing

**Symptoms:** complaints show `triaged_by = rules:fallback`; Stats page → "Fallback: yes (TriageTimeout / TriageRateLimited / TriageMalformedOutput …)".
Citizens are **not** affected: they still get 201 and a rules-based category. Operators are: triage quality drops.

1. **How bad?**
   ```bash
   curl -s -H 'Host: civicpulse.local' http://127.0.0.1/api/meta/providers | jq '{active, cache_hit_rate, recent: [.recent[] | {provider, fallback, error, latency_ms}]}'
   curl -s localhost:8000/metrics | grep triage_fallback_total    # (port-forward first on k8s)
   $k logs -l app=backend --tail=1000 | jq -c 'select(.msg=="triage fallback") | {complaint_id, provider, error_class}'
   ```
2. **Read the `error_class`:**
   | error_class | Meaning | Action |
   |---|---|---|
   | `TriageRateLimited` | Free-tier quota (429) | Wait, lower `RATE_LIMIT_REQUESTS`, or switch model. The content-hash cache already dedupes repeats |
   | `TriageTimeout` | Provider slower than 10 s | Check the provider's status page; consider a smaller model |
   | `TriageBadRequest` | 4xx: bad key, or the model was renamed/retired | Check `LLM_API_KEY` and `LLM_MODEL`; rotate the key if revoked |
   | `TriageMalformedOutput` | Model returned off-schema JSON | Usually a model change; pin a different `LLM_MODEL` |
   | `TriageUpstreamError` | 5xx / network | Provider outage; or on Compose, check that the backend is on the `edge` network |
3. **Switch provider** (no rebuild, same image):
   ```bash
   $k patch configmap civicpulse-config -p '{"data":{"TRIAGE_PROVIDER":"rules"}}'
   $k rollout restart deployment/backend
   ```
   Options: `rules` (always works), `ollama` (offline; Compose `--profile ollama`), `llm`.
4. **Rotate the key:**
   ```bash
   $k create secret generic civicpulse-secrets --from-literal=POSTGRES_PASSWORD="$($k get secret civicpulse-secrets -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d)" \
     --from-literal=LLM_API_KEY='<new key>' --dry-run=client -o yaml | kubectl apply -f -
   $k rollout restart deployment/backend
   ```
   Then update the `LLM_API_KEY` GitHub Secret so the next CD run uses it.

## 5. Other checks

| Question | Command |
|---|---|
| Is a pod out of rotation? | `$k get endpoints backend`, then `$k describe pod <pod>` (readiness `/ready` names the failed dependency) |
| Does Postgres keep its data? | `$k delete pod postgres-0`, wait, and the complaint count is unchanged (PVC `data-postgres-0`) |
| Is the rate limiter working? | 11 fast POSTs → the 11th is `429` with `Retry-After` |
| Is the stats cache working? | `curl -sI …/api/stats \| grep X-Cache` twice: MISS then HIT |
| HPA state | `$k get hpa backend-hpa -w` |
