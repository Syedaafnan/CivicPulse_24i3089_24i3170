#!/usr/bin/env bash
# Record HPA replicas and CPU every 5 s while a load test runs → CSV for the replicas-vs-load chart.
#   ./scripts/record-hpa.sh docs/evidence/hpa-run1.csv &      # start recording
#   k6 run -e BASE_URL=http://civicpulse.local load/k6-script.js
set -euo pipefail
OUT=${1:-hpa.csv}
echo "timestamp,seconds,current_replicas,desired_replicas,cpu_utilisation_pct" > "$OUT"
start=$(date +%s)
while true; do
  now=$(date +%s)
  read -r cur des cpu < <(kubectl -n civicpulse get hpa backend-hpa -o \
    jsonpath='{.status.currentReplicas} {.status.desiredReplicas} {.status.currentMetrics[0].resource.current.averageUtilization}{"\n"}' \
    || echo "0 0 0")
  echo "$(date -u +%FT%TZ),$((now - start)),${cur:-0},${des:-0},${cpu:-0}" | tee -a "$OUT"
  sleep 5
done
