#!/usr/bin/env bash
#
# Roll back SentryOps application deployments in Kubernetes to their previous revision.
#
# Usage:
#   scripts/k8s-rollback.sh [--yes]
#
# Options:
#   --yes    Skip confirmation prompt and execute the rollback immediately.
#
# This script targets only stateless application Deployments in the sentryops
# namespace. It does NOT roll back databases (PostgreSQL), StatefulSets, PVCs,
# or observability infrastructure.

set -euo pipefail

NAMESPACE="${NAMESPACE:-sentryops}"

if ! command -v kubectl >/dev/null 2>&1; then
  echo "error: kubectl is not installed or not on PATH" >&2
  exit 1
fi

if ! kubectl cluster-info >/dev/null 2>&1; then
  echo "error: no reachable Kubernetes cluster. Start minikube/kind/Docker Desktop Kubernetes." >&2
  exit 1
fi

if ! kubectl get namespace "${NAMESPACE}" >/dev/null 2>&1; then
  echo "error: namespace '${NAMESPACE}' does not exist. Cannot rollback." >&2
  exit 1
fi

DEPLOYMENTS=(
  "backend"
  "frontend"
  "api-gateway"
  "order-service"
  "payment-service"
  "notification-service"
  "user-service"
  "fault-injection"
)

echo "The following deployments in namespace '${NAMESPACE}' will be rolled back:"
for d in "${DEPLOYMENTS[@]}"; do
  echo "  - deployment/${d}"
done
echo ""

if [[ "${1:-}" != "--yes" ]]; then
  read -r -p "Are you sure you want to proceed with the rollback? [y/N] " response
  if [[ "${response}" != "y" && "${response}" != "Y" ]]; then
    echo "Rollback cancelled."
    exit 0
  fi
fi

echo "==> Initiating rollback..."

for d in "${DEPLOYMENTS[@]}"; do
  if kubectl get deployment "${d}" -n "${NAMESPACE}" >/dev/null 2>&1; then
    echo "    Rolling back deployment/${d}"
    kubectl rollout undo "deployment/${d}" -n "${NAMESPACE}"
  else
    echo "    warning: deployment/${d} not found in namespace ${NAMESPACE}, skipping."
  fi
done

echo "==> Waiting for rollback rollouts to complete..."
for d in "${DEPLOYMENTS[@]}"; do
  if kubectl get deployment "${d}" -n "${NAMESPACE}" >/dev/null 2>&1; then
    echo "    waiting for deployment/${d}"
    kubectl rollout status "deployment/${d}" -n "${NAMESPACE}" --timeout=180s
  fi
done

echo "==> Rollback complete."