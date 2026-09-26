#!/bin/sh
# Run by the Compose `migrate` service and the Kubernetes init container.
# Safe to run concurrently (advisory locks) and repeatedly (Alembic + idempotent seed).
set -eu
alembic upgrade head
if [ "${SEED_DEMO_DATA:-true}" = "true" ]; then
  python -m app.seed
fi
