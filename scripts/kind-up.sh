#!/usr/bin/env bash
# The "second command": put CivicPulse on a local Kubernetes cluster (kind).
#   ./scripts/kind-up.sh              # cluster + add-ons + images + dev overlay
#   ./scripts/kind-up.sh --vpa-full   # also install the VPA recommender
# Needs: docker, kind (>=0.25), kubectl. Afterwards: http://civicpulse.local (see /etc/hosts note below).
set -euo pipefail
cd "$(dirname "$0")/.."
CLUSTER=civicpulse

if ! kind get clusters | grep -qx "$CLUSTER"; then
  kind create cluster --config k8s/kind-config.yaml --wait 120s
fi
kubectl config use-context "kind-$CLUSTER"

./scripts/cluster-addons.sh "${1:-}"

echo "==> building and loading images"
docker build -t civicpulse-backend:dev backend
docker build -t civicpulse-frontend:dev frontend
kind load docker-image civicpulse-backend:dev civicpulse-frontend:dev --name "$CLUSTER"

echo "==> namespace + secret (before any pod starts: Postgres reads its password only on first init)"
kubectl create namespace civicpulse --dry-run=client -o yaml | kubectl apply -f -
if ! kubectl -n civicpulse get secret civicpulse-secrets >/dev/null 2>&1; then
  kubectl -n civicpulse create secret generic civicpulse-secrets \
    --from-literal=POSTGRES_PASSWORD="$(openssl rand -hex 24)" \
    --from-literal=LLM_API_KEY="${LLM_API_KEY:-}"
fi

echo "==> applying k8s/overlays/dev"
kubectl apply -k k8s/overlays/dev

kubectl -n civicpulse rollout status statefulset/postgres --timeout=180s
kubectl -n civicpulse rollout status deployment/redis --timeout=120s
kubectl -n civicpulse rollout status deployment/backend --timeout=300s
kubectl -n civicpulse rollout status deployment/frontend --timeout=120s
kubectl -n civicpulse get pods,svc,ingress,hpa

cat <<MSG

CivicPulse is running.
  Add once:  echo "127.0.0.1 civicpulse.local" | sudo tee -a /etc/hosts
  Open:      http://civicpulse.local
  Or:        curl -H 'Host: civicpulse.local' http://127.0.0.1/api/stats
MSG
