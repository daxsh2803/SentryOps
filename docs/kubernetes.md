# SentryOps on Kubernetes (Phase 13)

Phase 13 makes SentryOps deployable to a **local** Kubernetes cluster while
preserving the existing application architecture. It is deployment
infrastructure only — it is **not** an autonomous Kubernetes remediation
feature (see [Safety boundary](#safety-boundary)).

```text
Docker Compose  ->  Local Kubernetes        (this phase)
                ->  Cloud Kubernetes        (later phase, not implemented)
```

---

## 1. Architecture

Everything runs in a single dedicated namespace, `sentryops`. No application
workload is deployed into `default`.

| Workload | Kind | Port(s) | Image | Purpose |
|---|---|---|---|---|
| `postgres` | StatefulSet | 5432 | `pgvector/pgvector:pg16` | Incident data + pgvector |
| `redis` | Deployment | 6379 | `redis:7-alpine` | Fault-injection state |
| `backend` | Deployment | 8000 | `sentryops/backend:local` | Incident API + AI investigation |
| `frontend` | Deployment | 80 | `sentryops/frontend:local` | Operator dashboard (nginx) |
| `api-gateway` | Deployment | 8000 | `sentryops/api-gateway:local` | Simulated production entry point |
| `order-service` | Deployment | 8001 | `sentryops/order-service:local` | Simulated production |
| `payment-service` | Deployment | 8002 | `sentryops/payment-service:local` | Simulated production |
| `notification-service` | Deployment | 8003 | `sentryops/notification-service:local` | Simulated production |
| `user-service` | Deployment | 8004 | `sentryops/user-service:local` | Simulated production |
| `fault-injection` | Deployment | 8005 | `sentryops/fault-injection:local` | Fault injection API |
| `prometheus` | Deployment | 9090 | `prom/prometheus:latest` | Metrics |
| `loki` | Deployment | 3100 | `grafana/loki:latest` | Logs |
| `jaeger` | Deployment | 16686, 4317, 4318 | `jaegertracing/all-in-one:latest` | Traces |
| `grafana` | Deployment | 3000 | `grafana/grafana:latest` | Dashboards |

### Traffic flow

```text
Browser ──► frontend (NodePort 30080)
                │  nginx serves the SPA
                └─ /api/* ─proxy─► backend:8000 ──► postgres:5432
                                        │
                                        ├─► prometheus:9090   (metrics queries)
                                        ├─► loki:3100         (log queries)
                                        ├─► jaeger:16686      (trace queries)
                                        └─► fault-injection:8005

simulated production ──► redis:6379
                     └─► loki / jaeger (logs + traces)
prometheus ──scrape──► api-gateway, order, payment, notification, user
```

### Why nginx proxies `/api`

The frontend is built with `VITE_API_URL=/api`, and nginx forwards `/api/` to
`http://backend:8000/`. This keeps the browser on a **single origin**, so no
CORS configuration change to the backend was required and only one Service has
to be exposed externally.

### Storage

| Volume | Type | Why |
|---|---|---|
| `data-postgres-0` | `volumeClaimTemplates` (2Gi, RWO) | Database must survive pod replacement |
| Redis | none | Holds only disposable fault-injection keys |
| Prometheus / Loki / Grafana | `emptyDir` | Local-development convenience; see [Known limitations](#known-limitations) |

### Configuration and secrets

Three ConfigMaps plus one Secret:

| Object | Contents |
|---|---|
| `sentryops-config` | `POSTGRES_HOST/PORT/DB/USER`, `REDIS_URL` (shared) |
| `backend-config` | `LOKI_URL` (query base), `PROMETHEUS_URL`, `JAEGER_URL`, `FAULT_API_URL`, `MOCK_LLM` |
| `microservices-config` | `LOKI_URL` (**push** URL), `OTLP_ENDPOINT`, `ORDER_/PAYMENT_/NOTIFICATION_SERVICE_URL` |
| `sentryops-secrets` | `POSTGRES_PASSWORD`, `DATABASE_URL` |

> `LOKI_URL` intentionally appears twice with **different** values. The Python
> microservices build a Loki *push* client (`.../loki/api/v1/push`), while the
> backend log agent issues LogQL *queries* against `http://loki:3100`. A single
> shared value would break one of the two.

---

## 2. Prerequisites

* Docker (running)
* `kubectl`
* One local cluster: **Minikube**, **kind**, or **Docker Desktop Kubernetes**
* Images are built locally — **no registry and no `docker push` are required**

Suggested local resources: 4 CPUs and ~6 GB RAM free for the cluster.

---

## 3. Start a local cluster

Pick one:

```bash
# Minikube
minikube start --cpus=4 --memory=6144

# kind
kind create cluster --name sentryops

# Docker Desktop: Settings -> Kubernetes -> Enable Kubernetes
kubectl config use-context docker-desktop
```

Confirm the cluster is reachable:

```bash
kubectl cluster-info
kubectl get nodes
```

---

## 4. Build and load the images

```bash
scripts/k8s-build-images.sh
```

This builds all eight application images from the existing Dockerfiles and loads
them into the cluster (auto-detects Minikube/kind, otherwise assumes a shared
Docker daemon such as Docker Desktop).

Manual equivalent:

```bash
docker build -t sentryops/backend:local             backend
docker build -t sentryops/frontend:local            frontend
docker build -t sentryops/api-gateway:local         microservices/api-gateway
docker build -t sentryops/order-service:local       microservices/order-service
docker build -t sentryops/payment-service:local     microservices/payment-service
docker build -t sentryops/notification-service:local microservices/notification-service
docker build -t sentryops/user-service:local        microservices/user-service
docker build -t sentryops/fault-injection:local     fault-injection

# Minikube only:
minikube image load sentryops/backend:local   # ...repeat per image

# kind only:
kind load docker-image sentryops/backend:local  # ...repeat per image
```

---

## 5. Deploy

```bash
scripts/k8s-deploy.sh
```

The script performs four steps:

1. create the `sentryops` namespace
2. create the observability ConfigMaps **from the existing Compose config files**
3. `kubectl apply -k k8s/`
4. wait for `postgres`, `redis`, `backend` and `frontend` to roll out

### Why step 2 is separate

kustomize refuses to read files outside its own root directory, so
`k8s/observability/` cannot reference `../../observability/...`. Rather than
**duplicating** the Prometheus/Loki/Grafana configuration into `k8s/` (which
would create two sources of truth that drift), the ConfigMaps are generated from
the original files at deploy time.

Manual equivalent of step 2:

```bash
kubectl apply -f k8s/namespace.yaml

kubectl create configmap prometheus-config -n sentryops \
  --from-file=prometheus.yml=observability/prometheus/prometheus.yml \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create configmap loki-config -n sentryops \
  --from-file=local-config.yaml=observability/loki/loki-config.yml \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create configmap grafana-datasources -n sentryops \
  --from-file=datasources.yml=observability/grafana/provisioning/datasources/datasources.yml \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create configmap grafana-dashboard-provider -n sentryops \
  --from-file=dashboards.yml=observability/grafana/provisioning/dashboards/dashboards.yml \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create configmap grafana-dashboards -n sentryops \
  --from-file=observability.json=observability/grafana/dashboards/observability.json \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -k k8s/
```

> Running `kubectl apply -k k8s/` **without** first creating those ConfigMaps
> leaves the observability pods in `CreateContainerConfigError`.

---

## 6. Verify

```bash
kubectl get namespaces
kubectl get pods -n sentryops
kubectl get services -n sentryops
kubectl get deployments -n sentryops
kubectl get statefulsets -n sentryops
kubectl get pvc -n sentryops
```

All pods should reach `Running` with `READY 1/1`. `data-postgres-0` should be
`Bound`.

### Application health (pod health alone is not proof)

```bash
# Backend through the frontend's same-origin proxy:
kubectl port-forward -n sentryops svc/frontend 8080:80
curl http://localhost:8080/api/health
# {"status":"ok","service":"backend"}

# Backend directly:
kubectl port-forward -n sentryops svc/backend 8000:8000
curl http://localhost:8000/health

# Database connectivity from inside the cluster:
kubectl exec -n sentryops statefulset/postgres -- \
  pg_isready -U sentryops -d sentryops

# Redis connectivity:
kubectl exec -n sentryops deployment/redis -- redis-cli ping

# Incident workflow end to end:
curl -X POST http://localhost:8000/incidents \
  -H 'Content-Type: application/json' \
  -d '{"title":"k8s smoke test","severity":"LOW","affected_service":"payment-service"}'
curl http://localhost:8000/incidents
```

### Observability

```bash
kubectl port-forward -n sentryops svc/grafana 3000:3000      # http://localhost:3000
kubectl port-forward -n sentryops svc/prometheus 9090:9090   # http://localhost:9090
kubectl port-forward -n sentryops svc/jaeger 16686:16686     # http://localhost:16686
```

Prometheus targets should show the simulated production services as `UP`.

---

## 7. Access the dashboard

```bash
# Minikube
minikube service frontend -n sentryops

# Docker Desktop
# http://localhost:30080

# Anything else
kubectl port-forward -n sentryops svc/frontend 8080:80
# http://localhost:8080
```

---

## 8. Resilience test

This is the point of introducing Kubernetes.

```bash
# 1. Pods are recreated automatically
kubectl get pods -n sentryops -l app=backend
kubectl delete pod -n sentryops -l app=backend
kubectl get pods -n sentryops -l app=backend -w   # a new pod appears

# 2. The backend becomes healthy again
kubectl rollout status deployment/backend -n sentryops

# 3. Database data survives pod replacement
kubectl exec -n sentryops statefulset/postgres -- \
  psql -U sentryops -d sentryops -c "CREATE TABLE IF NOT EXISTS k8s_persistence_probe(id int);"
kubectl delete pod -n sentryops postgres-0
kubectl rollout status statefulset/postgres -n sentryops
kubectl exec -n sentryops statefulset/postgres -- \
  psql -U sentryops -d sentryops -c "SELECT to_regclass('k8s_persistence_probe');"
# The table still exists because the PVC was re-bound, not recreated.

# 4. Scaling is possible without redesign
kubectl scale deployment/backend -n sentryops --replicas=2
kubectl scale deployment/backend -n sentryops --replicas=1
```

---

## 9. Teardown

```bash
kubectl delete namespace sentryops
# or, keeping the namespace:
kubectl delete -k k8s/
```

Deleting the namespace also deletes the PostgreSQL PVC. To remove the cluster
itself:

```bash
minikube delete          # or: kind delete cluster --name sentryops
```

---

## 10. Configuration reference

### Overriding credentials

The committed Secret contains **local-development placeholders** that match
`docker-compose.yml`. For anything beyond a throwaway cluster, replace it:

```bash
kubectl delete secret sentryops-secrets -n sentryops
kubectl create secret generic sentryops-secrets -n sentryops \
  --from-literal=POSTGRES_PASSWORD='<strong-password>' \
  --from-literal=DATABASE_URL='postgresql+psycopg2://sentryops:<strong-password>@postgres:5432/sentryops'
```

Then remove `secret.yaml` from `k8s/kustomization.yaml` so a re-apply cannot
revert it.

### Changing configuration

Edit the ConfigMaps in `k8s/configmap.yaml` and re-apply, then restart the
affected workload:

```bash
kubectl apply -k k8s/
kubectl rollout restart deployment/backend -n sentryops
```

---

## 11. Known limitations

* **Observability data is not persisted.** Prometheus, Loki and Grafana use
  `emptyDir`, so history is lost when a pod is replaced. Durable dashboards and
  TSDB storage are deferred to the cloud phase.
* **Observability images use `:latest`**, matching `docker-compose.yml`. Pin
  digests before relying on reproducibility.
* **No ingress controller.** External access uses a single NodePort
  (`frontend:30080`). On kind this requires a node port mapping at cluster
  creation; `kubectl port-forward` always works.
* **Single replica per workload.** Scaling is possible (`kubectl scale`) but was
  not exercised for stateless services beyond the backend.
* **No HPA, no PodDisruptionBudget, no ResourceQuota.** Deliberately out of
  scope for a local deployment.
* **PostgreSQL runs as a single StatefulSet replica** — no replication or
  failover.

---

## 12. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ImagePullBackOff` / `ErrImageNeverPull` | Images not loaded into the cluster | Re-run `scripts/k8s-build-images.sh` |
| `CreateContainerConfigError` on observability pods | ConfigMaps missing | Run `scripts/k8s-deploy.sh` (step 2) |
| Backend stuck in `Init:0/1` | PostgreSQL not ready yet | `kubectl get pods -n sentryops -l app=postgres`; check logs |
| `data-postgres-0` stays `Pending` | No default StorageClass | `kubectl get storageclass`; enable one or add `storageClassName` |
| Frontend loads but API calls fail | nginx cannot reach the backend Service | `kubectl exec -n sentryops deploy/frontend -- nginx -T`; check `svc/backend` |
| Pods evicted / `Pending` | Cluster out of resources | Give the cluster more CPU/RAM |

Useful commands:

```bash
kubectl describe pod -n sentryops <pod>
kubectl logs -n sentryops <pod>
kubectl logs -n sentryops <pod> --previous
kubectl get events -n sentryops --sort-by=.lastTimestamp
```

---

## 13. Safety boundary

Phase 13 adds **deployment infrastructure, not execution capability**.

* **No RBAC objects.** No `ClusterRole`, `ClusterRoleBinding`, `Role`,
  `RoleBinding` or `ServiceAccount` is created, and nothing references
  `cluster-admin`.
* **No service account tokens.** Every application pod sets
  `automountServiceAccountToken: false`, so a container has no credentials to
  reach the Kubernetes API.
* **No kubectl in containers.** No workload image, command or argument invokes
  `kubectl` or a Kubernetes client.
* **No privileged containers or host access.** No `privileged: true`, no
  `hostPath`, no `hostNetwork`.

The remediation boundary is unchanged:

```text
AI decision -> structured action -> deterministic allow-list -> risk engine
            -> approval gate -> controlled simulated action -> verification
```

Kubernetes does **not** become a new path in that chain. If a future phase adds
autonomous Kubernetes remediation, it must pass through the same allow-list,
risk and approval gates — never `LLM -> kubectl`.

---

## 14. Metrics Server (Phase 14)

SentryOps includes the Kubernetes Metrics Server, allowing resource utilization tracking.

**Purpose**: The Metrics Server supplies resource metrics (CPU and Memory) to Kubernetes APIs like `kubectl top` and Horizontal Pod Autoscaler (HPA). Note that it does *not* automatically configure Prometheus dashboards or alerting.

**Deployment**: The metrics server is deployed automatically as part of `scripts/k8s-deploy.sh` using kustomize and is isolated in the `kube-system` namespace. The `k8s/metrics-server/kustomization.yaml` fetches the official manifest and patches it to support the local kind cluster (`--kubelet-insecure-tls`).

**Verification**:
```bash
kubectl top nodes
kubectl top pods -n sentryops
```

**Known limitations**:
- The `--kubelet-insecure-tls` flag is insecure for production and must be removed if this configuration is adopted for cloud environments.
