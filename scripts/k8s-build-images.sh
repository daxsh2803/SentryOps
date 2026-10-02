#!/usr/bin/env bash
#
# Build every SentryOps image locally and make it available to the local
# Kubernetes cluster. No registry and no `docker push` are involved.
#
# The existing Dockerfiles are reused as-is; only the frontend image is new
# (there was no frontend container definition before Phase 13).
#
# Usage:
#   scripts/k8s-build-images.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_PREFIX="${IMAGE_PREFIX:-sentryops}"
TAG="${TAG:-local}"

# name:build-context
IMAGES="
backend:backend
frontend:frontend
api-gateway:microservices/api-gateway
order-service:microservices/order-service
payment-service:microservices/payment-service
notification-service:microservices/notification-service
user-service:microservices/user-service
fault-injection:fault-injection
"

if ! command -v docker >/dev/null 2>&1; then
  echo "error: docker is not installed or not on PATH" >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "error: the Docker daemon is not reachable. Start Docker Desktop first." >&2
  exit 1
fi

for entry in $IMAGES; do
  name="${entry%%:*}"
  context="${entry#*:}"
  echo "==> building ${IMAGE_PREFIX}/${name}:${TAG} from ${context}/"
  docker build -t "${IMAGE_PREFIX}/${name}:${TAG}" "${ROOT}/${context}"
done

echo
echo "==> loading images into the local cluster"

load_image() {
  local image="$1"

  # Minikube keeps its own image store.
  if command -v minikube >/dev/null 2>&1 && minikube status >/dev/null 2>&1; then
    minikube image load "${image}"
    return
  fi

  # kind runs nodes as containers with their own image store.
  if command -v kind >/dev/null 2>&1 && [ -n "$(kind get clusters 2>/dev/null)" ]; then
    kind load docker-image --name "${KIND_CLUSTER:-sentryops}" "${image}"
    return
  fi

  # Docker Desktop Kubernetes and similar share the local Docker daemon, so the
  # images are already visible to the cluster. Nothing to do.
  echo "    no minikube/kind cluster detected; assuming a shared Docker daemon"
}

for entry in $IMAGES; do
  name="${entry%%:*}"
  load_image "${IMAGE_PREFIX}/${name}:${TAG}"
done

echo
echo "Done. Built and loaded:"
docker images --filter "reference=${IMAGE_PREFIX}/*:${TAG}" --format '  {{.Repository}}:{{.Tag}}'
