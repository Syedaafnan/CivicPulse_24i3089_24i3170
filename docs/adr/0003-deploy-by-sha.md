# ADR 0003: Deploy by immutable reference (digest), not by mutable tag

## Status
Accepted

## Context
`:latest` is a mutable pointer — it can be repointed at a different image at any time, which means
"what is production running?" has no reliable answer, and a rollback that re-deploys `:latest`
might redeploy the very image you're trying to roll back from. The assignment treats deploying
`:latest` as an automatic deduction, and requires that "what is production running?" have a
one-word answer pastable into `git show`.

## Decision
`cd.yml`'s `build-push` job builds and pushes each image to GHCR tagged with both the commit SHA
and `latest` (`cd.yml:58,72` — `latest` is pushed for convenience/browsability only), and captures
each image's **content digest** as a job output (`cd.yml:36-37`). The `deploy-k8s` job never
references either tag when deploying — it builds `BACKEND_REF`/`FRONTEND_REF` directly from those
digest outputs (`cd.yml:121-122`) and renders the prod overlay against them via
`kustomize edit set image ...@<digest>` (`cd.yml:174`).

As a guardrail against this regressing silently, the same job greps the rendered manifest and
fails the pipeline if it finds `:latest`, an unresolved `set-by-cd` placeholder, or an unresolved
`/OWNER/` placeholder anywhere in it (`cd.yml:176`), rather than trusting that every future edit to
the workflow preserves the digest-only invariant.

Every publish/deploy job is also gated with an explicit `needs:` dependency on the job that
verified the code (tests → build-push → deploy-k8s), so nothing is ever published or deployed from
a commit that hasn't passed CI.

## Consequences
- "What is production running?" has a literal one-word answer: the digest recorded in the
  `deploy-k8s` job's logs (or, once GitOps/Cosign are in play, the value attached to the signed
  image) — not a tag that could have moved since the deploy happened.
- Rollback has two supported mechanisms, and they answer different questions: `kubectl rollout undo
  deployment/backend -n civicpulse` is the fast, imperative "go back one step" answer for an
  incident at 3 a.m.; re-applying the previous overlay pinned to the previous digest is the slower,
  declarative, auditable answer once the fire is out and the change needs to be reviewable in git.
- The cost is extra plumbing — the digest has to be threaded through job outputs across three jobs
  (`build-push` → `deploy-k8s`) rather than just re-reading a tag — which is why the guard script
  exists: it's cheap insurance against a future edit reintroducing a tag-based deploy path by
  accident.
