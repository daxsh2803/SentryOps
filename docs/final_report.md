# SentryOps — Final Technical Project Report

**Autonomous Multi-Agent Production Incident Response & Root Cause Analysis Platform**

---

## Executive Summary

SentryOps is a multi-agent AI operations platform designed to autonomously investigate production incidents, perform evidence-grounded root cause analysis, propose allowlisted remediations, enforce deterministic human-in-the-loop safety gates, and verify recovery.

Operating in a local Kubernetes cluster (`sentryops` namespace), SentryOps integrates with production observability tooling (Prometheus, Loki, Jaeger, and Grafana). It demonstrates an observable incident response lifecycle while enforcing strict architectural boundaries: **LLMs never execute raw shell commands, never hold cluster-admin tokens, and never directly mutate Kubernetes infrastructure.**

---

## 1. System Architecture

```text
                               +-----------------------------+
                               |     Frontend Dashboard      |
                               |  (React 19, TypeScript,     |
                               |   Vite, NodePort 30080)     |
                               +--------------+--------------+
                                              |
                                     /api (same-origin proxy)
                                              |
                                              v
+------------------------+     +-----------------------------+     +-------------------------+
| Observability Stack    |     |       FastAPI Backend       |     | PostgreSQL + pgvector   |
| - Prometheus (9090)    |<--->|   Incident Lifecycle &      |<--->| Incidents, Evidence,    |
| - Loki (3100)          |     |   LangGraph Multi-Agent AI  |     | RCA, Runbook Vector DB  |
| - Jaeger (16686/4317)  |     +--------------+--------------+     +-------------------------+
| - Grafana (3000)       |                    |
+------------------------+                    |
                                              v
+--------------------------------------------------------------------------------------------+
| Microservices Simulated Production (FastAPI)                                               |
| - api-gateway (8000)  - order-service (8001)  - payment-service (8002)                      |
| - notification-service (8003)  - user-service (8004)  - fault-injection (8005)             |
+--------------------------------------------------------------------------------------------+
```

### Key Architectural Components
1. **Simulated Production Workloads**: Five core FastAPI microservices communicating over HTTP with OpenTelemetry tracing and structured JSON logging.
2. **Fault Injection Framework**: Dedicated `fault-injection` API (port 8005) with Redis backing to dynamically inject controlled faults (`http_500_spike`, `payment_service_crash`, `artificial_latency`, `db_connection_exhaustion`, `bad_configuration`).
3. **Observability Pipeline**: OpenTelemetry SDK export to Jaeger, Prometheus scrape targets for all services, Loki log shipping, and a multi-panel Grafana dashboard.
4. **Knowledge Base (RAG)**: PostgreSQL with `pgvector` storing embeddings of historical runbooks and postmortems for semantic similarity retrieval.

---

## 2. Multi-Agent AI Investigation Framework

The AI investigation pipeline is implemented as a state machine using **LangGraph**:

1. **Trigger & Fan-Out (`IncidentManager`)**:
   - Spawns six specialized investigative agents running concurrently:
     - **Log Agent**: Queries Loki for application errors and error stack traces.
     - **Metrics Agent**: Queries Prometheus for rate/error/duration metrics.
     - **Trace Agent**: Queries Jaeger for failed spans and error tags.
     - **Deployment Agent**: Inspects configuration and synthetic fault states.
     - **Infrastructure Agent**: Queries container/pod health and restart counts.
     - **Knowledge Agent (RAG)**: Retrieves top-$k$ runbooks from PostgreSQL via vector similarity search.
2. **Fan-In & Root Cause Analysis (`RCAAgent`)**:
   - Synthesizes findings from all six collectors.
   - Prevents hallucination by strictly verifying evidence links against actually collected evidence IDs.
3. **Remediation & Deterministic Risk Policy (`RemediationAgent` & `RiskEngine`)**:
   - Restricts proposals to an explicit allowlist: `RESTART_SERVICE`, `SCALE_SERVICE`, `ROLLBACK_SERVICE`.
   - Evaluated by a hardcoded, deterministic (non-LLM) risk policy:
     - `LOW` Risk: Restarting a single replica (eligible for automated action).
     - `MEDIUM` / `HIGH` Risk: Multi-replica operations, scaling, configuration rollbacks (mandates `PENDING_APPROVAL`).
4. **Human-in-the-Loop Gate**:
   - Actions requiring approval block until an operator submits an explicit decision via `POST /incidents/{id}/approve` or `POST /incidents/{id}/reject`.
5. **Execution & Deterministic Verification (`VerificationAgent`)**:
   - Approved actions execute against controlled execution handlers.
   - The Verification Agent validates recovery criteria deterministically (replica counts, health endpoints).

---

## 3. Experimental Demonstration & Rehearsal Evidence

The demonstration was rehearsed and verified using the controlled `http_500_spike` incident on `payment-service`. The recorded metrics are preserved in `docs/images/demo/demo_results.json`:

### Summary of Workload Measurements
| Phase | Duration / Workload | Success Count | Failure Count | Average Latency | Service Health |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Baseline** | 10 requests | 10 (100%) | 0 (0%) | 1.116s | Healthy |
| **Fault Active** (`http_500_spike`) | 10 requests | 0 (0%) | 10 (100%) | 1.008s | Critical (HTTP 500) |
| **Post-Cleanup Recovery** | 10 requests | 10 (100%) | 0 (0%) | 1.051s | Healthy (Recovered) |

### Incident Lifecycle Walkthrough (Incident `INC-CD90E2`)
1. **Detection**: Fault injected (`FAULT-1D8A4DA5`); traffic failure detected; incident created (`INC-CD90E2`).
2. **Telemetry Harvested**:
   - Jaeger Traces (`EV-TRACE-3F77AC`): 10 traces analyzed; 7 error spans found.
   - Synthetic Fault Registry (`EV-CHANGE-9964BD`): Detected active `http_500_spike`.
   - Prometheus Infrastructure (`EV-INFRA-5B1A7A`): Pod health inspected.
   - Knowledge Retrieval (`EVID-KNOW-6750`): 3 historical runbooks retrieved.
3. **Proposal & Risk Gate**:
   - Remediation ID: `21`.
   - Proposal: `SCALE_SERVICE` for `payment-service` to 2 replicas, explicitly labeled `[DEMO FIXTURE - MOCK_LLM]`.
   - Risk Assessment: `MEDIUM` (`requires_approval: true`). Halted at `PENDING_APPROVAL`.
4. **Operator Approval & Verification**:
   - Operator approved via dashboard (`POST /incidents/INC-CD90E2/approve`).
   - Execution status: `SUCCESS`.
   - Verification status: `VERIFIED_SUCCESS` (both `replica_count` and `service_health` checks passed).
   - Incident transitioned to `RESOLVED`.
5. **Rejection Path Validation (Incident `INC-28EE86`)**:
   - Tested rejection workflow via `POST /incidents/INC-28EE86/reject`.
   - Approval resolved to `REJECTED`; remediation execution remained `null`; incident remained in `INVESTIGATING`.

### Critical Boundary: Telemetry vs. Simulated Actuation
- **Real Production Telemetry**: The Prometheus metrics, Loki logs, and Jaeger traces reflect genuine network calls and active faults in the Kubernetes cluster.
- **Simulated Remediation**: The remediation engine mutates in-memory state (`SIMULATED_INFRA_STATE`) only.
- **Zero Real Kubernetes Actuation**: Inspection of the cluster deployment (`kubectl get deployment payment-service -n sentryops`) confirms that live replicas remained at `1` throughout. Real HTTP recovery was caused strictly by clearing the synthetic fault via `POST /faults/FAULT-1D8A4DA5/cleanup`.

---

## 4. Test Suite Execution & Disclosure

### Kubernetes-Compatible & Deterministic Suites: 152 / 152 PASSED (100%)
The modern test suites covering the Kubernetes architecture and deterministic safety lifecycle pass with complete success:
```bash
python -m pytest -o pythonpath=backend \
  tests/test_phase7_knowledge_agent.py \
  tests/test_phase8_workflow_demo.py \
  tests/test_phase8_remediation.py \
  tests/test_phase9_verification.py \
  tests/test_phase11_evaluation.py \
  tests/test_phase12_replay_postmortem.py \
  tests/test_phase13_kubernetes.py -v
```
- **Results**: 152 passed, 0 failed, 0 skipped in 27.78s.
- **Frontend Production Build**: `npm run build` (`tsc -b && vite build`) passed with 0 errors in 1.96s.

### Full Repository Suite Disclosure: 169 Passed / 15 Failed (184 Total)
When executing `pytest tests/` across the entire repository:
- **169 tests passed**, **15 tests failed**, **98 warnings**.
- **Root Cause of Failures**: All 15 failures are legacy integration tests designed for Docker Compose host port mappings:
  - 6 tests hardcoded `BACKEND_API = "http://127.0.0.1:8080"` (which hits the API gateway on Kubernetes port-forwarding rather than the backend on port 8000).
  - 7 tests attempted direct socket connections to microservice host ports `8001–8004` (which are internal Kubernetes `ClusterIP` services not forwarded to the host).
  - 2 tests assumed API gateway was exposed on port 8000.
- **Genuine Code Regressions**: **0**.

---

## 5. Security & Operational Limitations

1. **Authentication & Authorization**: The FastAPI backend contains no token or session-based authentication middleware; all incident creation and approval endpoints are unauthenticated in this local prototype.
2. **Default Credentials**: Hardcoded credentials (`sentryops:sentryops`) are used across `docker-compose.yml`, `k8s/secret.yaml`, and Grafana provisioning.
3. **Local Kind TLS**: The Metrics Server deployment includes `--kubelet-insecure-tls` to permit scraping in the local Kind development cluster.
4. **Ephemeral Observability Storage**: Prometheus, Loki, and Grafana utilize Kubernetes `emptyDir` volumes; metric and log histories do not persist across pod restarts.
5. **No Direct Cluster Actuator**: The platform contains no direct Kubernetes client (`kubectl` or Python client) in the agent execution chain.

---

## 6. Conclusion

SentryOps proves the viability of a multi-agent AI incident response platform when backed by deterministic safety gates, structured evidence verification, and mandatory human approval. The platform provides verifiable SRE workflows while completely eliminating unconstrained LLM risk.
