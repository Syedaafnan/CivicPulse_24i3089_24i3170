#!/usr/bin/env bash
# End-to-end smoke test through the public entry point (Compose frontend or k8s Ingress).
#   scripts/smoke.sh http://localhost:8080                 # Compose
#   scripts/smoke.sh http://127.0.0.1 civicpulse.local     # Ingress (Host header)
# Asserts: POST → 201 with a triage result, GET by id, category in schema (and == $EXPECT_CATEGORY if set),
# X-Cache MISS → HIT.
set -euo pipefail
BASE=${1:?base url}
HOST=${2:-}
H=(); [[ -n "$HOST" ]] && H=(-H "Host: $HOST")

echo "==> waiting for the API through $BASE"
for i in $(seq 1 60); do
  code=$(curl -s -o /dev/null -w '%{http_code}' "${H[@]}" "$BASE/api/meta/enums" || true)
  [[ "$code" == 200 ]] && break
  [[ $i == 60 ]] && { echo "API never became reachable (last status $code)"; exit 1; }
  sleep 2
done

echo "==> POST /api/complaints"
body=$(curl -sf "${H[@]}" -X POST "$BASE/api/complaints" -H 'Content-Type: application/json' \
  -d '{"text":"Burst water main flooding Street 12 since fajr, water entering houses","location":"G-11/3, Islamabad"}')
id=$(jq -r .id <<<"$body"); category=$(jq -r .category <<<"$body"); by=$(jq -r .triaged_by <<<"$body")
echo "    id=$id category=$category priority=$(jq -r .priority <<<"$body") triaged_by=$by"

echo "==> GET /api/complaints/$id"
got=$(curl -sf "${H[@]}" "$BASE/api/complaints/$id")
[[ $(jq -r .id <<<"$got") == "$id" ]] || { echo "GET returned a different complaint"; exit 1; }
# With a live LLM "correct" means "in our schema", not "a specific word": the category must be one of
# the server's enums. Deterministic runs (TRIAGE_PROVIDER=simulated/rules) also pin the exact value.
enums=$(curl -sf "${H[@]}" "$BASE/api/meta/enums" | jq -r '.categories[]')
grep -qx "$category" <<<"$enums" || { echo "category '$category' is not a valid enum value"; exit 1; }
if [[ -n "${EXPECT_CATEGORY:-}" && "$category" != "$EXPECT_CATEGORY" ]]; then
  echo "expected category $EXPECT_CATEGORY, got $category"; exit 1
fi

echo "==> X-Cache MISS then HIT"
first=$(curl -s -D - -o /dev/null "${H[@]}" "$BASE/api/stats" | tr -d '\r' | awk -F': ' 'tolower($1)=="x-cache"{print $2}')
second=$(curl -s -D - -o /dev/null "${H[@]}" "$BASE/api/stats" | tr -d '\r' | awk -F': ' 'tolower($1)=="x-cache"{print $2}')
echo "    first=$first second=$second"
[[ "$first" == MISS && "$second" == HIT ]] || { echo "cache did not go MISS → HIT"; exit 1; }

echo "SMOKE TEST PASSED"
