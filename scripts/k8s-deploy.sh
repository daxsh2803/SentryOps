#!/usr/bin/env bash
#
# Deploy SentryOps to the current Kubernetes context.
#
# Steps:
#   1. create the namespace
#   2. create the observability ConfigMaps from the SAME files Docker Compose
#      mounts (kustomize cannot read files outside its own root, so these are
#      created here instead of being duplicated into k8s/)
#   3. apply the kustomization
#   4. wait for the core workloads to roll out
#
# Usage:
#   scripts/k8s-deploy.sh
#
# Prerequisites: a running local cluster and images built by
# scripts/k8s-build-images.sh.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAMESPACE="${NAMESPACE:-sentryops}"

if ! command -v kubectl >/dev/null 2>&1; then
  echo "error: kubectl is not installed or not on PATH" >&2
  exit 1
fi

if ! kubectl cluster-info >/dev/null 2>&1; then
  echo "error: no reachable Kubernetes cluster. Start minikube/kind/Docker Desktop Kubernetes." >&2
  exit 1
fi

echo "==> creating namespace ${NAMESPACE}"
kubectl apply -f "${ROOT}/k8s/namespace.yaml"

echo "==> creating observability ConfigMaps from existing config files"

create_configmap() {
  local name="$1"
  shift
  kubectl create configmap "${name}" -n "${NAMESPACE}" "$@" \
    --dry-run=client -o yaml | kubectl apply -f -
}

create_configmap prometheus-config \
  --from-file=prometheus.yml="${ROOT}/observability/prometheus/prometheus.yml"
create_configmap loki-config \
  --from-file=local-config.yaml="${ROOT}/observability/loki/loki-config.yml"
create_configmap grafana-datasources \
  --from-file=datasources.yml="${ROOT}/observability/grafana/provisioning/datasources/datasources.yml"
create_configmap grafana-dashboard-provider \
  --from-file=dashboards.yml="${ROOT}/observability/grafana/provisioning/dashboards/dashboards.yml"
create_configmap grafana-dashboards \
  --from-file=observability.json="${ROOT}/observability/grafana/dashboards/observability.json"

echo "==> applying kustomization"
kubectl apply -k "${ROOT}/k8s"

echo "==> waiting for core workloads"
for deployment in postgres redis backend frontend; do
  echo "    waiting for deployment/${deployment}"
  kubectl rollout status "deployment/${deployment}" -n "${NAMESPACE}" --timeout=180s || true
done
# postgres is a StatefulSet, not a Deployment.
kubectl rollout status "statefulset/postgres" -n "${NAMESPACE}" --timeout=180s || true

cat <<EOF

Applied. Inspect with:
  kubectl get pods -n ${NAMESPACE}
  kubectl get services -n ${NAMESPACE}
  kubectl get deployments -n ${NAMESPACE}
  kubectl get pvc -n ${NAMESPACE}

Access the dashboard:
  minikube:       minikube service frontend -n ${NAMESPACE}
  Docker Desktop: http://localhost:30080
EOF
