# SentryOps — Master Presentation Slides

---

## Slide 1: Title & Overview
### SentryOps
**Autonomous Multi-Agent Production Incident Response & Root Cause Analysis Platform**

- **Domain**: Site Reliability Engineering (SRE), Autonomous Operations, Observability
- **Core Technology**: Python, FastAPI, LangGraph, React 19, TypeScript, Kubernetes, PostgreSQL + pgvector
- **Core Principle**: *Empowering multi-agent AI incident investigation under strict, deterministic safety guardrails.*

---

## Slide 2: The Problem
### The Modern Production Incident Dilemma

- **Alert Fatigue & Fragmented Telemetry**: SREs lose critical time correlating logs across Loki, metrics across Prometheus, and traces across Jaeger during high-severity outages.
- **Prolonged MTTR**: Manual root-cause diagnosis consumes 80%+ of incident triage time.
- **The Danger of Unconstrained AI**: Giving an LLM direct shell access or unconstrained `kubectl` execution creates catastrophic reliability and security risks (hallucinated commands, accidental data deletion, cascading outages).

---

## Slide 3: The SentryOps Solution
### Architecture & Safety-First Philosophy

- **Simulated Production**: 5 FastAPI microservices (`order`, `payment`, `notification`, `user`, `api-gateway`) + dynamic fault-injection API on Kubernetes.
- **End-to-End Observability**: OpenTelemetry instrumentation exporting to Prometheus, Loki, and Jaeger, visualised in Grafana.
- **Multi-Agent Orchestration**: LangGraph orchestrates parallel investigative agents with structured fan-in synthesis.
- **Deterministic Guardrails**:
  - Remediations restricted to a strict allowlist (`RESTART_SERVICE`, `SCALE_SERVICE`, `ROLLBACK_SERVICE`).
  - Non-LLM Risk Engine classifies actions (`LOW`, `MEDIUM`, `HIGH`).
  - Mandatory Human Approval Gate for medium/high risk actions.
  - Zero direct `kubectl` actuation by agents.

---

## Slide 4: Multi-Agent Parallel Investigation
### LangGraph Fan-Out / Fan-In Workflow

```text
               +-------------------+
               |  Incident Trigger |
               +---------+---------+
                         |
                 [IncidentManager]
                         |
      +-------+-------+--+---+-------+-------+
      |       |       |      |       |       |
    [Log]  [Metric] [Trace] [Deploy] [Infra] [Knowledge]
    (Loki)  (Prom)  (Jaeger) (Faults) (Health) (pgvector)
      |       |       |      |       |       |
      +-------+-------+--+---+-------+-------+
                         |
                     [RCAAgent]
           (Evidence Linkage & Validation)
                         |
                 [RemediationAgent]
                         |
             [Deterministic Risk Engine]
```

- **Anti-Hallucination Gate**: The RCA Agent strictly verifies that all cited evidence IDs exist in the incident evidence store before generating conclusions.

---

## Slide 5: Deterministic Risk Policy & Approval Gate
### Human-in-the-Loop Operational Safety

| Risk Level | Policy Rule | Autonomous Action Allowed? | Operator Action Required |
|:---:|:---|:---:|:---:|
| **LOW** | Restarting single unhealthy service instance | Yes (Simulated) | None (Auto-proceeds to Verification) |
| **MEDIUM** | Scaling service replicas | **No** | **Mandatory Operator Approval** |
| **HIGH** | Multi-instance restarts, configuration rollback | **No** | **Mandatory Operator Approval** |

- **State Enforcement**: Any proposal requiring approval halts at `PENDING_APPROVAL`.
- **Approval API**: `POST /incidents/{id}/approve` transitions status to `APPROVED` and executes controlled action.
- **Rejection API**: `POST /incidents/{id}/reject` transitions status to `REJECTED`, cancels execution, and leaves incident in `INVESTIGATING`.

---

## Slide 6: Observable Telemetry & Operator Dashboard
### Real-Time Visibility Across the Stack

1. **Grafana Observability Dashboard**:
   - Panel 1: **Service Health Status** (Stat panel showing all 5 microservices as HEALTHY / DOWN).
   - Panel 2: **Request Rate** (Per-second throughput across instances).
   - Panel 3: **Error Rate (5xx)** (Spikes during active faults; returns to 0 on recovery).
   - Panel 4: **P95 Latency** (Histogram quantile latency across active routes).
   - Panel 5: **Live Service Logs** (Loki log streaming filtered by `service_name`).
2. **Jaeger Distributed Tracing**:
   - End-to-end trace waterfalls exposing failed downstream HTTP requests with error tags.
3. **React 19 SRE Dashboard**:
   - Real-time incident timeline, evidence inventory, RCA summary, approval card, verification checks, evaluation score, and structured postmortem.

---

## Slide 7: Live Demonstration Walkthrough
### Validated Scenario: `http_500_spike` on `payment-service`

- **Incident Identifier**: `INC-CD90E2`
- **Fault Type**: Synthetic HTTP 500 failure injection (`FAULT-1D8A4DA5`)

```text
Baseline (10/10 OK) ──► Fault Active (0/10 OK, 10/10 500s) ──► Fault Cleanup (10/10 OK)
 Avg Latency: 1.116s           Avg Latency: 1.008s               Avg Latency: 1.051s
```

- **Evidence Harvested**:
  - `EV-TRACE-3F77AC`: 10 Jaeger traces analyzed (7 error spans identified).
  - `EV-CHANGE-9964BD`: Active synthetic fault metadata detected.
  - `EV-INFRA-5B1A7A`: Prometheus node/pod infrastructure health verified.
  - `EVID-KNOW-6750`: 3 relevant historical runbooks retrieved from pgvector.
- **Proposal**: `SCALE_SERVICE` for `payment-service` (`replicas: 2`), labeled `[DEMO FIXTURE - MOCK_LLM]`.
- **Risk Gate**: Rated `MEDIUM`, halted at `PENDING_APPROVAL`.

---

## Slide 8: Execution, Verification & Postmortem
### Deterministic Lifecycle Completion

- **Approval**: Operator submitted approval via dashboard.
- **Execution Result**: Status `SUCCESS` against in-memory `SIMULATED_INFRA_STATE`.
- **Deterministic Verification**:
  - Check 1 (`replica_count`): 2 replicas running (Passed).
  - Check 2 (`service_health`): healthy (Passed).
  - Outcome: `VERIFIED_SUCCESS` $\rightarrow$ Incident marked `RESOLVED`.
- **Incident Replay & Evaluation**:
  - Evaluation Framework scored response as `PASS` across all 4 dimensions (Investigation, RCA, Remediation, Verification).
  - Replay Consistency: `MATCH` (Original vs Replay verified without historical re-execution).
  - Postmortem: 9 structured sections generated deterministically.

---

## Slide 9: Technical Testing & Metric Disclosure
### Evidence-Based Quality Assurance

- **Selected Kubernetes-Compatible Suites**: **152 / 152 PASSED (100%)**
  - Covers Phase 7 Knowledge Agent, Phase 8 Workflow Demo, Phase 8 Remediation, Phase 9 Verification, Phase 11 Evaluation, Phase 12 Replay/Postmortem, and Phase 13 Kubernetes architecture.
  - Zero failures, zero skipped in 27.78s.
- **Frontend Production Build**: `npm run build` completed cleanly in 1.96s with zero compile errors.
- **Full Repository Test Suite Disclosure**:
  - **169 Passed**, **15 Failed** out of 184 total tests.
  - The 15 failures are exclusively legacy Docker Compose integration tests asserting obsolete host port mappings (`BACKEND_API = "http://127.0.0.1:8080"` vs `8000`, and direct host ports `8001–8004` which are internal Kubernetes ClusterIPs).
  - **0 Code Regressions** across all core application logic.

---

## Slide 10: Security Architecture & Operational Boundaries
### Built-in Hardened Constraints

1. **No Pod Privilege Escalation**:
   - All application pods configure `automountServiceAccountToken: false`.
   - Zero RBAC roles or cluster-admin bindings exist.
2. **No Real Cluster Actuation**:
   - `kubectl get deployment payment-service` remained strictly at 1 replica throughout the demo.
   - LLM agents have no access to shell or Kubernetes APIs.
3. **Disclosed Local Development Limitations**:
   - FastAPI backend has no token-based authentication middleware (local prototype scope).
   - Local default credentials (`sentryops:sentryops`) used in development manifests.
   - Kind Metrics Server uses `--kubelet-insecure-tls` for local container scraping.

---

## Slide 11: Summary & Future Roadmap
### Key Achievements & Next Steps

- **Achievements**:
  - Complete, observable, multi-agent incident response lifecycle.
  - 100% passing Kubernetes-compatible test suites (152/152).
  - Deterministic safety gates preventing AI hallucination and unauthorized actuation.
  - Full-stack integration with Prometheus, Loki, Jaeger, Grafana, and React 19 UI.
- **Future Roadmap**:
  - Integration with production LLM providers (e.g. Claude 3.5 Sonnet / GPT-4o) using same deterministic safety gates.
  - Multi-tenant RBAC and API key authentication on incident management endpoints.
  - GitOps-driven Kubernetes actuation (PR-based remediation proposals via ArgoCD).
  - Persistent volume provisioning for cloud observability backends (EKS/GKE).
