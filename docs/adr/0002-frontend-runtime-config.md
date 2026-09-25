# ADR 0002: Frontend runtime configuration

## Status
Accepted

## Context
Vite bakes every `import.meta.env.*` value into the built JavaScript bundle at **build** time. If
the backend's API URL were read that way, the resulting Docker image would only be valid for the
environment it was built for — deploying the same image to a second environment (dev cluster,
prod cluster, a teammate's laptop) would silently call the wrong backend. That breaks
build-once-deploy-many, which the assignment treats as a first-class requirement for the frontend
image.

## Decision
We used two complementary mechanisms rather than picking one:

1. **nginx proxies `/api` to the backend** (`frontend/default.conf.template`), so in the common
   case the frontend's own JavaScript never needs to know an absolute backend URL at all — it just
   calls `/api/...` on its own origin, and nginx forwards it server-side.

2. **A `config.js` is generated at container *start*, not at build time**
   (`frontend/docker-entrypoint.d/40-runtime-config.sh`), rendered from environment variables
   (e.g. `APP_ENVIRONMENT`) when the container boots, and served as a static file the app loads
   before its own bundle. `frontend/src/config.ts` reads this at runtime via
   `window.__CIVICPULSE_CONFIG__`, never via `import.meta.env`. The version of `config.js`
   committed to the repo (`frontend/public/config.js`) is explicitly a dev-time placeholder,
   overwritten by the entrypoint script on every container start.

We kept both instead of relying on the proxy alone because the proxy only covers same-origin
deployment topologies; the runtime-generated config gives us an escape hatch for any environment
where the frontend needs to know something else at boot (e.g. which environment name to display),
without rebuilding the image.

## Consequences
- One frontend image (`frontend/Dockerfile`) is built once in CI and deployed unchanged to dev and
  prod overlays and to a developer's local Compose stack — the only thing that differs between
  environments is the environment variables passed to the running container, never the image
  contents.
- The cost is an extra moving part at container startup (the entrypoint script must run before
  nginx starts serving) — if that script fails silently, the app would load with a stale
  placeholder config. We accept this because the failure mode is visible (wrong/missing API calls
  in the browser console) rather than silent data corruption.
- Any future config value the frontend needs at runtime (feature flags, a different API base for a
  specific overlay, etc.) should be added to the same `40-runtime-config.sh` template and
  `config.ts` reader, not to `import.meta.env`, to avoid reintroducing the baked-URL problem this
  ADR exists to prevent.
