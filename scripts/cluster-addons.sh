#!/usr/bin/env bash
# Install what the manifests rely on: ingress-nginx, metrics-server (HPA needs it), VPA.
# Usage: scripts/cluster-addons.sh [--vpa-full]
#   default     → only the VPA CRD (enough to apply backend-vpa; no recommendations)
#   --vpa-full  → full VPA (recommender etc.), needed for `kubectl describe vpa backend-vpa`
set -euo pipefail
INGRESS_NGINX=controller-v1.12.0
METRICS_SERVER=v0.7.2
VPA=vertical-pod-autoscaler-1.2.1

echo "==> ingress-nginx ($INGRESS_NGINX)"
kubectl apply -f "https://raw.githubusercontent.com/kubernetes/ingress-nginx/${INGRESS_NGINX}/deploy/static/provider/kind/deploy.yaml"

echo "==> metrics-server ($METRICS_SERVER)"
kubectl apply -f "https://github.com/kubernetes-sigs/metrics-server/releases/download/${METRICS_SERVER}/components.yaml"
# kind's kubelets use self-signed certs
kubectl -n kube-system patch deployment metrics-server --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]' || true

if [[ "${1:-}" == "--vpa-full" ]]; then
  echo "==> VPA full install ($VPA)"
  tmp=$(mktemp -d)
  git clone --depth 1 --branch "$VPA" https://github.com/kubernetes/autoscaler.git "$tmp/autoscaler"
  (cd "$tmp/autoscaler/vertical-pod-autoscaler" && ./hack/vpa-up.sh)
else
  echo "==> VPA CRD only ($VPA)"
  kubectl apply -f "https://raw.githubusercontent.com/kubernetes/autoscaler/${VPA}/vertical-pod-autoscaler/deploy/vpa-v1-crd-gen.yaml"
fi

echo "==> waiting for ingress-nginx and metrics-server"
kubectl -n ingress-nginx rollout status deployment/ingress-nginx-controller --timeout=180s
kubectl -n kube-system rollout status deployment/metrics-server --timeout=180s
