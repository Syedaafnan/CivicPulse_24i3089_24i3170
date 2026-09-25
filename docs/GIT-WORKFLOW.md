# Git workflow and commit plan: two partners, 35+ commits each

This covers rubric section **A (15 marks)** and the automatic deductions in §5.3:

| Rubric line | How this plan meets it |
|---|---|
| main protected: PR, CI, ≥1 approval, screenshot | Step 1 (branch protection) + screenshot into `docs/evidence/` |
| dev + feature branches, nothing committed to main | Every change goes to `feat/*` → PR → `dev`; `main` only receives `dev` via PR |
| ≥5 merged PRs, each linked to an Issue, each with a real review comment from your partner | 15 PRs below, each with `Closes #N`, each reviewed by the other partner |
| ≥35 commits, conventional prefixes, neither partner below 35% | 42 planned commits each (~50/50) |
| One deliberate merge conflict on real code | Step 6 |
| **−5** for commits pushed directly to main | Branch protection makes it impossible, including for admins |

---

## 0. Before anything: the "does my commit count?" checklist

`git shortlog -sn` counts commits by **author name and email**. If your laptop's Git email isn't one GitHub knows, your commits won't link to your account and can show up as a third "person".

```bash
git config --global user.name  "Your Real Name"
git config --global user.email "the-email-on-your-github-account@example.com"
git config --global pull.rebase true        # linear history when you pull
git config --global init.defaultBranch main
```

Check on GitHub → Settings → Emails that the email is listed. Use the **same** name and email on every machine.

> ⚠️ **Never "Squash and merge".** It turns a 7-commit PR into 1 commit, and the squash is credited to whoever clicks merge. That is how teams lose their commit count. Use **"Create a merge commit"** (or "Rebase and merge").

---

## 1. One-time repository setup (Partner A does this, Partner B watches)

1. Create the GitHub repo `civicpulse` (public, or private with both instructors added). Add Partner B under **Settings → Collaborators**.
2. First commit on `main` (README + .gitignore only), then create `dev`:
   ```bash
   git switch -c dev && git push -u origin dev
   ```
3. **Settings → General → Pull Requests**: untick *Allow squash merging*, keep *Allow merge commits*, tick *Automatically delete head branches*.
4. **Settings → Branches → Add rule** for `main`:
   - ✅ Require a pull request before merging → Required approvals: **1**
   - ✅ Dismiss stale approvals when new commits are pushed
   - ✅ Require status checks to pass (add the CI jobs once `ci.yml` exists)
   - ✅ Require branches to be up to date before merging
   - ✅ **Do not allow bypassing the above settings** (this covers admins too)
   - ✅ Block force pushes
5. Optional but nice: the same rule on `dev` with 1 approval, so every feature PR must be reviewed.
6. Screenshot the rule page → `docs/evidence/branch-protection.png`.
7. **Issues**: create one Issue per PR in the table below (#1 … #15), assign each to its owner, and use labels `backend`, `frontend`, `ai`, `devops`, `docs`.

---

## 2. The daily loop (both partners, every time)

```bash
git switch dev && git pull                      # start from the latest dev
git switch -c feat/10-triage-service            # branch name = type/issue-number-topic

# ...work on ONE small thing, run the tests...
git add -p                                      # stage deliberately, hunk by hunk
git commit -m "feat(triage): add triage service with rules fallback"
# repeat: commit every time one small thing works (aim for 2–4 commits per working session)

git push -u origin feat/10-triage-service
gh pr create --base dev --title "feat: triage service with fallback and content-hash cache" \
  --body "Closes #10

## What
- ...
## How to test
- pytest tests/test_api.py -k fallback
"
```

**Partner reviews** (this is marked, so make it real):

```bash
gh pr checkout 10 && pytest          # actually run it
gh pr review 10 --comment -b "Fallback path looks right. Question: why don't we cache the rules:fallback result? If Groq is down for an hour we re-call it for every duplicate. (I think not caching is correct: otherwise a rules answer gets pinned for 24h. Can you add a comment saying so?)"
gh pr review 10 --approve
```

A *substantive* comment asks a question, spots a bug, or suggests a change. "LGTM 👍" doesn't count. The author answers with a commit (`fix(triage): …` or `docs(triage): explain why fallback isn't cached`), which is one more real commit for the author.

**Merge** with "Create a merge commit". Closing keywords only fire when a PR merges into the *default* branch, so either close the Issue by hand after merging into `dev`, or link it from the PR's *Development* sidebar.

**Keeping a long branch current**: `git fetch && git rebase origin/dev` (before you push) or `git merge origin/dev` (after you've pushed and someone reviewed).

**Releases**: when a set of features is done, open a PR `dev → main`, have your partner approve it once CI is green, and merge it. Plan on 2–3 of these across the two weeks.

---

## 3. Who owns what

Split so that **each of you owns backend code *and* something else**. The viva asks each of you about your partner's code too (viva factor 0.75 if you're shaky on it), so review every PR properly.

- **Partner A**: backend core: domain + state machine, data layer (models, Alembic, repository, seed), complaint/stats services, routes, Redis cache and rate limiter, ops endpoints (health/ready/metrics, logging, SIGTERM), backend image.
- **Partner B**: AI layer (every triage provider, prompt guardrail, retry/fallback, content-hash cache, meta endpoints), the whole frontend, frontend image + nginx, `compose.yaml`.

Phase 2 (Docker/k8s/CI/CD) is split the same way; see the Phase 2 table in §4.

---

## 4. The commit plan (42 + 42)

Each row is one commit. Build it in this order and commit when that piece works, with its tests green. The reference code in this repo already contains every piece. Don't paste it all at once: rebuild it file by file, run it, understand it, adapt it, then commit.

### Partner A: backend core

| PR / branch | # | Commit message |
|---|---|---|
| **#1** `chore/1-repo-setup` | 1 | `chore: initialize repository with README and LICENSE` |
| | 2 | `chore: add .gitignore and .env.example` |
| | 3 | `build(backend): add pyproject with ruff, mypy and pytest config` |
| | 4 | `build(backend): pin runtime and dev requirements` |
| **#2** `feat/2-domain-and-schema` | 5 | `feat(backend): add settings loaded from environment` |
| | 6 | `feat(domain): add category, priority and status enums` |
| | 7 | `feat(domain): add explicit status transition table` |
| | 8 | `test(domain): cover valid, invalid and terminal transitions` |
| | 9 | `feat(db): add engine and session factory` |
| | 10 | `feat(db): map complaints table with check constraints` |
| | 11 | `feat(db): add Alembic environment reading DATABASE_URL` |
| | 12 | `feat(db): add initial complaints migration with enum types` |
| | 13 | `feat(db): add (status, priority) and created_at indexes` |
| **#3** `feat/3-repository-and-seed` | 14 | `feat(repo): add complaint repository add and get` |
| | 15 | `feat(repo): add filtered paginated listing with total` |
| | 16 | `feat(repo): add aggregate queries for stats` |
| | 17 | `feat(seed): add 34 Urdu-influenced seed complaints` |
| | 18 | `feat(seed): make seed idempotent with uuid5 ids` |
| | 19 | `test(seed): assert a second seed run inserts nothing` |
| **#4** `feat/4-complaints-api` | 20 | `feat(api): add request and response schemas` |
| | 21 | `feat(services): add complaint service create/get/list` |
| | 22 | `feat(services): enforce state machine on status change` |
| | 23 | `feat(api): add complaints routes` |
| | 24 | `feat(api): return 400 with field-level validation errors` |
| | 25 | `feat(api): map domain errors to 404 and 409` |
| | 26 | `test(api): cover create, get, list, pagination and 409` |
| **#5** `feat/5-redis-cache-rate-limit` | 27 | `feat(cache): add Redis JSON cache that fails open` |
| | 28 | `feat(stats): add read-through stats cache with X-Cache header` |
| | 29 | `feat(stats): invalidate stats cache on write` |
| | 30 | `feat(ratelimit): add distributed fixed-window rate limiter` |
| | 31 | `feat(api): return 429 with Retry-After on POST /api/complaints` |
| | 32 | `test(cache): cover MISS→HIT→invalidate and 429` |
| **#6** `feat/6-ops-endpoints` | 33 | `feat(ops): add /health liveness that never touches the DB` |
| | 34 | `feat(ops): add /ready checking Postgres and Redis` |
| | 35 | `feat(logging): add JSON logs with request_id contextvar` |
| | 36 | `feat(ops): add request-id and metrics middleware` |
| | 37 | `feat(ops): expose Prometheus /metrics` |
| | 38 | `feat(server): drain in-flight requests on SIGTERM` |
| | 39 | `test(ops): cover health, ready, draining and metrics` |
| **#7** `build/7-backend-image` | 40 | `build(backend): add multi-stage non-root Dockerfile` |
| | 41 | `build(backend): add .dockerignore` |
| | 42 | `docs: document backend setup and API table in README` |

### Partner B: AI layer + frontend

| PR / branch | # | Commit message |
|---|---|---|
| **#8** `feat/8-triage-interface` | 1 | `feat(triage): add TriageResult schema and provider protocol` |
| | 2 | `feat(triage): add triage error taxonomy` |
| | 3 | `feat(triage): add rule-based keyword provider` |
| | 4 | `test(triage): cover rule-based classification` |
| | 5 | `feat(triage): add simulated provider with failure injection` |
| | 6 | `feat(triage): select provider from TRIAGE_PROVIDER` |
| **#9** `feat/9-llm-provider` | 7 | `feat(triage): add guarded prompt with delimited complaint text` |
| | 8 | `feat(triage): validate model output against the schema` |
| | 9 | `test(triage): reject prose, off-enum and oversized output` |
| | 10 | `feat(triage): add Groq provider with JSON mode and 10s timeout` |
| | 11 | `feat(triage): retry once with jitter on timeout, 429 and 5xx` |
| | 12 | `test(triage): cover retry, no retry on 400, key never in repr` |
| | 13 | `feat(triage): add Ollama provider` |
| **#10** `feat/10-triage-service` | 14 | `feat(triage): add triage service with rules fallback` |
| | 15 | `feat(triage): log one warning per fallback` |
| | 16 | `feat(triage): cache results by content hash for 24h` |
| | 17 | `feat(meta): add /api/meta/providers with last 20 outcomes` |
| | 18 | `feat(meta): add /api/meta/enums` |
| | 19 | `test(triage): always-raising provider still returns 201` |
| | 20 | `test(triage): prompt injection cannot choose the category` |
| **#11** `feat/11-frontend-scaffold` | 21 | `build(frontend): scaffold React + Vite + TypeScript` |
| | 22 | `build(frontend): add eslint and vitest config` |
| | 23 | `feat(frontend): generate API types from OpenAPI schema` |
| | 24 | `feat(frontend): add typed API client with ApiError` |
| | 25 | `feat(frontend): read runtime config from /config.js` |
| | 26 | `feat(frontend): add app shell, routing and error boundary` |
| **#12** `feat/12-submit-view` | 27 | `feat(frontend): add submit form mirroring server validation` |
| | 28 | `feat(frontend): show honest loading state and triage result` |
| | 29 | `test(frontend): cover validation, loading, fallback and 429` |
| **#13** `feat/13-dashboard-view` | 30 | `feat(frontend): add paginated filterable dashboard` |
| | 31 | `feat(frontend): change status and show server 409 verbatim` |
| | 32 | `test(frontend): cover transitions, 409 and filters` |
| **#14** `feat/14-stats-view` | 33 | `feat(frontend): add stats view with X-Cache badge` |
| | 34 | `feat(frontend): show provider, hit rate and fallback history` |
| | 35 | `test(frontend): cover stats view and error boundary` |
| | 36 | `test(frontend): check validation limits against OpenAPI` |
| **#15** `build/15-frontend-image-compose` | 37 | `build(frontend): add non-root nginx config with /api proxy` |
| | 38 | `build(frontend): generate config.js at container start` |
| | 39 | `build(frontend): add multi-stage Dockerfile and .dockerignore` |
| | 40 | `build: add compose.yaml with edge and internal networks` |
| | 41 | `build: add healthchecks, volumes and migrate service` |
| | 42 | `docs: add quickstart and screenshots to README` |

### Phase 2: Docker, Kubernetes, CI/CD (≈20 more each)

| PR / branch | Owner | Commits |
|---|---|---|
| **#16** `build/16-compose-prod` | B | `build: add compose.prod.yaml using GHCR images by IMAGE_TAG` · `build(backend): add migrate.sh used by compose and k8s` · `fix(db): serialise concurrent migrations with an advisory lock` · `fix(seed): lock seeding so concurrent init containers don't race` |
| **#17** `feat/17-k8s-base` | A | `feat(k8s): add namespace, configmap and placeholder secret` · `feat(k8s): add postgres statefulset with volumeClaimTemplates` · `feat(k8s): add redis deployment with PVC and AOF` · `feat(k8s): add backend deployment with migrate init container` · `feat(k8s): add startup, liveness and readiness probes` · `feat(k8s): add rolling update, preStop and grace period` · `feat(k8s): add frontend deployment and ClusterIP services` · `feat(k8s): add ingress routing / and /api` |
| **#18** `feat/18-k8s-scaling` | A | `feat(k8s): add backend HPA with tuned behaviour` · `feat(k8s): add VPA in recommender mode` · `feat(k8s): add pod disruption budgets` · `feat(k8s): restrict postgres and redis to backend pods` · `docs: add scaling runbook and HPA recorder script` |
| **#19** `feat/19-k8s-overlays` | B | `feat(k8s): add dev overlay for local kind images` · `feat(k8s): add prod overlay deploying by digest` · `build: add kind config and cluster add-ons script` · `build: add kind-up.sh one-command cluster deploy` · `test: add k6 load script for HPA and rollout demos` |
| **#20** `ci/20-ci-workflow` | A | `ci: add lint-and-type job for backend and frontend` · `ci: add backend and frontend test jobs` · `ci: build both images without pushing` · `ci: scan images with pinned trivy` · `ci: validate manifests with kustomize and kubeconform` · `ci: add compose integration smoke job` · `ci: assert frontend cannot reach postgres` |
| **#21** `ci/21-cd-release` | B | `ci: add cd workflow gated on the full test suite` · `ci: push images to GHCR tagged by commit sha` · `ci: emit SBOMs with syft` · `ci: sign images with cosign and verify before deploy` · `ci: deploy prod overlay by digest to ephemeral kind` · `ci: smoke-test the ingress after rollout` · `ci: add release workflow for semver tags` · `ci: add dependabot for actions, pip, npm and docker` |
| **#22** `docs/22-runbook` | B | `docs: add runbook for deploy, rollback, logs and triage failures` · `docs: document CI/CD in README` |

Then the evidence commits (`docs(evidence): …`), one for each screenshot or capture, split between you.

On top of these you'll naturally get `fix:` commits from review feedback, the conflict-resolution commit, and the later k8s/CI/docs work, so both of you will end up well over 35.

**Dependencies:** B's #10 needs A's #4 (`ComplaintService` calls the triage service), and the frontend (#11–#14) talks to A's API. Start B on #8/#9 (standalone) and A on #1–#4 in week 1. B can build the frontend against `npm run dev` with the backend running locally.

### Suggested timeline (2 weeks)

| Days | Partner A | Partner B |
|---|---|---|
| 1–2 | #1, #2 | Issues + #8 |
| 3–4 | #3, #4 | #9 |
| 5–6 | #5 | #10 (after #4 merges) + **merge conflict (step 6)** |
| 7–8 | #6 | #11, #12 |
| 9–10 | #7, release PR `dev → main` | #13, #14 |
| 11–14 | k8s / CI work, reviews | #15, CD/docs work, reviews, release PR |

Commit as you actually work. Don't batch a week of work into one evening, and never backdate commits: timestamps and PR history are visible to the instructors.

---

## 5. Commit message rules (Conventional Commits)

```
<type>(<optional scope>): <imperative summary, ≤ 72 chars, no full stop>

<optional body: WHY, not what>
```

Types: `feat` new behaviour · `fix` bug fix · `test` tests only · `docs` docs only · `refactor` no behaviour change · `build` Dockerfiles, deps, compose · `ci` workflows · `chore` housekeeping.

Good: `fix(ratelimit): key by X-Real-IP so nginx doesn't collapse all clients into one`
Bad: `update`, `changes`, `final`, `fixed stuff`, `WIP`.

---

## 6. The deliberate merge conflict (3 marks)

It has to be on **real code**, so use a line you both genuinely need to change: the router registration in `backend/app/main.py`.

1. Both branches start from the same `dev` where the line is
   `for r in (complaints.router,):`
2. **Partner A**, on `feat/5-redis-cache-rate-limit`, adds the stats router:
   `for r in (complaints.router, stats.router):` → commit, PR, merge into `dev`.
3. **Partner B**, on `feat/10-triage-service`, adds the meta router on the same line:
   `for r in (complaints.router, meta.router):` → commit.
4. B updates their branch: `git fetch && git merge origin/dev` → **CONFLICT in backend/app/main.py**.
5. **Capture evidence before fixing**: screenshot the terminal output and the file with `<<<<<<<`/`=======`/`>>>>>>>` markers → `docs/evidence/conflict-markers.png`.
6. Resolve by keeping both routers, run `pytest`, then:
   ```bash
   git add backend/app/main.py
   git commit   # keep the default "Merge remote-tracking branch 'origin/dev' into feat/10-…" message, and add a body explaining the resolution
   ```
7. Screenshot `git log --graph --oneline -15` showing the merge → `docs/evidence/conflict-resolved.png`.
8. Write 2–4 sentences in `docs/evidence/CONFLICT.md`, e.g.: *"Both versions were correct but incomplete: A's added `/api/stats`, B's added `/api/meta/*`. Taking either side would have silently dropped an endpoint that the other partner's tests cover, so the resolution keeps both routers in one tuple. We confirmed it by running the full test suite after the merge."*

---

## 7. Checking your numbers

```bash
git shortlog -sn --no-merges dev      # per-person commit counts (paste this in the submission)
git shortlog -sne                     # shows emails; spot a "third person" caused by a wrong email
git log --oneline | grep -vcE '^[0-9a-f]+ (feat|fix|docs|test|refactor|build|ci|chore|perf|style)(\(.+\))?!?: '
                                      # commits NOT following the convention (should be 0 apart from merges)
```

If one of you has commits under two emails, add a `.mailmap` at the repo root:

```
Ali Khan <ali@github-email.com> <ali@laptop.local>
```

Target: **each ≥ 42 commits, and neither below 45% of the total**.

---

## 8. Things that cost marks (don't)

- Pushing to `main` directly (−5). Branch protection prevents it; don't turn it off "just once".
- Committing `.env` or any key, even briefly (−20, and the key must be rotated). A later "remove .env" commit doesn't help: **it's still in history**. If it happens, stop and rotate the key before anything else.
- Squash-merging PRs, which erases your commit count.
- Rubber-stamp reviews ("LGTM").
- One partner doing all the merges *and* all the commits; the 35% floor applies per person.
