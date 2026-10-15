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

## Slide 4: SentryOps End-to-End System Architecture
### Implemented Component Topology & Runtime Data Flow

```text
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │                              OPERATOR / BROWSER INTERFACE                              │
 │  • React 19 SRE Dashboard (:3080)  • Grafana (:3300)  • Jaeger Distributed Tracing (:16686) │
 └─────────────┬────────────────────────────────┬───────────────────────────┬─────────────┘
               │ HTTP / SPA API                 │ Telemetry Queries         │ Trace Inspect
               ▼                                ▼                           ▼
 ┌──────────────────────────────┐ ┌────────────────────────────────────────────────────────┐
 │   FRONTEND NGINX REVERSE     │ │                 OBSERVABILITY ENGINE                   │
 │   PROXY (Kubernetes Pod)     │ │  • Prometheus (:9090) - /metrics Scrapes               │
 │  /api         -> backend:8000│ │  • Loki (:3100)       - Structured JSON Log Streams    │
 │  /faults-api  -> fault:8005  │ │  • Jaeger (:16686)    - OpenTelemetry Distributed Traces│
 │  /gateway-api -> gateway:8000│ └─────────────────────────────▲──────────────────────────┘
 └───────┬───────────────┬──────┘                               │ Telemetry Push/Scrape
         │               │                                      │
         │ API Calls     │ Client Orders                        │
         ▼               ▼                                      │
 ┌───────────────┐ ┌────────────────────────────────────────────┴─────────────────────────┐
 │ CONTROLLED    │ │            SIMULATED PRODUCTION MICROSERVICES (Kubernetes)            │
 │ FAULT ENGINE  │ │                                                                      │
 │  • Fault API  │ │   [API Gateway:8000] ──► [Order Service:8001] ──► [Payment Service]  │
 │    (:8005)    │ │                                                     (Port 8002)      │
 │  • Redis      │ │   [Notification Service:8003]    [User Service:8004]         ▲       │
 │    (:6379)    │ │              ▲                              ▲                │       │
 └───────┬───────┘ └──────────────┼──────────────────────────────┼────────────────┼───────┘
         │ Active Fault State     │                              │                │
         └────────────────────────┴──────────────────────────────┴────────────────┘
                                  (Microservices poll Redis error/delay injection)
                                                 ▲
                                                 │ Investigation & Remediation
 ┌───────────────────────────────────────────────┴────────────────────────────────────────┐
 │               SENTRYOPS BACKEND & MULTI-AGENT ENGINE (FastAPI :8000)                   │
 │                                                                                        │
 │  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
 │  │                         LangGraph Orchestration Pipeline                         │  │
 │  │                                                                                  │  │
 │  │  [IncidentManager] ──► Fan-Out to 6 Parallel Specialized Investigative Agents:   │  │
 │  │   ├── LogAgent           ──► Queries Loki for error traces & logs                │  │
 │  │   ├── MetricsAgent       ──► Queries Prometheus HTTP error rate & latency spikes │  │
 │  │   ├── TraceAgent         ──► Queries Jaeger for downstream error spans           │  │
 │  │   ├── DeploymentAgent    ──► Queries Fault Injection API for active anomalies    │  │
 │  │   ├── InfrastructureAgent──► Inspects Kubernetes pod & node health               │  │
 │  │   └── KnowledgeAgent     ──► Queries pgvector for historical runbooks & incidents │  │
 │  │                                                                                  │  │
 │  │  [RCA Agent]             ──► Fan-In Evidence Synthesis + Anti-Hallucination Gate │  │
 │  │  [Remediation Agent]     ──► Strict Allowlist Selection (SCALE/RESTART/ROLLBACK) │  │
 │  │  [Deterministic Risk]    ──► Non-LLM Risk Classification (LOW / MEDIUM / HIGH)   │  │
 │  └──────────────────────────────────────────┬───────────────────────────────────────┘  │
 │                                             │                                          │
 │                                             ▼                                          │
 │  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
 │  │                        Deterministic Safety & Human Gate                         │  │
 │  │  • PENDING_APPROVAL: Halts execution for MEDIUM / HIGH risk proposals             │  │
 │  │  • Operator Approval / Rejection API (/incidents/{id}/approve or /reject)        │  │
 │  │  • Actuation Boundary: In-Memory SIMULATED_INFRA_STATE (0 real cluster mutations)│  │
 │  │  • Automated Verification: Asserts replica count & service health                │  │
 │  │  • Lifecycle Audit: Replay Reconstruction & 9-Section Structured Postmortem      │  │
 │  └──────────────────────────────────────────┬───────────────────────────────────────┘  │
 │                                             │                                          │
 │                                             ▼                                          │
 │  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
 │  │                     PostgreSQL Database with pgvector (:5432)                    │  │
 │  │   • incidents        • incident_events  • evidence       • root_causes           │  │
 │  │   • remediations     • approvals        • executions     • verifications         │  │
 │  │   • evaluations      • embeddings (semantic runbook search & historical RAG)     │  │
 │  └──────────────────────────────────────────────────────────────────────────────────┘  │
 └────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Key Architecture Principles Demonstrated
1. **Strict Service Separation**: Microservice workloads, telemetry collection, and incident response run as isolated Kubernetes pods within the `sentryops` namespace.
2. **Deterministic Safety Boundary**: LLM agents are strictly confined to evidence analysis; remediation actuation updates only simulated state, protecting live infrastructure.
3. **Evidence-Linked Auditability**: Every finding, root cause, remediation proposal, and verification result is persisted in PostgreSQL and linked to real observability artifacts.

---

## Slide 5: Multi-Agent Parallel Investigation
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
- **Input-to-Output Flow Summary**: Telemetry & Signals (Input) ➔ Parallel Investigation ➔ Risk Gate & Verification (Output).

---

## Slide 6: Deterministic Risk Policy & Approval Gate
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

## Slide 7: Project Input: What Goes Into SentryOps?
### Production Telemetry, Incident Signals, System Context & Operational Boundaries

```text
┌─────────────────────────────┐   ┌─────────────────────────────┐
│ Telemetry: Prom + Loki + Jg │ + │ Context: Faults + Runbooks  │
└──────────────┬──────────────┘   └──────────────┬──────────────┘
               └───────────────┬─────────────────┘
                               ▼
   [ LangGraph Multi-Agent Parallel Investigation Engine ]
```

#### Four Input Categories:
1. **A. Production Telemetry (Continuous Observability)**:
   - **Prometheus Metrics**: Request throughput, HTTP 5xx error rate, service health, and P95 latency across all services.
   - **Loki Logs**: Structured application error logs, stack traces, and exception details streamed by service name.
   - **Jaeger Traces**: End-to-end distributed traces capturing execution paths and isolating failed downstream spans.
2. **B. Incident and Failure Signals (Anomaly Triggers)**:
   - Live microservice failures, HTTP 500 error spikes, and latency anomalies.
   - Fault-injection scenarios (`http_500_spike`, crash, latency) injected via port 8005 in controlled demonstration.
3. **C. Incident Context & Knowledge Base (RAG)**:
   - Incident identifiers (`INC-CD90E2`), affected service (`payment-service`), timestamp, and status.
   - Collected evidence store linking metrics, logs, traces, and fault metadata.
   - Top-k historical runbooks and postmortems retrieved from PostgreSQL via pgvector semantic search (`EVID-KNOW-6750`).
4. **D. Operational Constraints & Policy Boundaries**:
   - Allowed remediation action types strictly restricted to `RESTART_SERVICE`, `SCALE_SERVICE`, `ROLLBACK_SERVICE`.
   - Parameter validation schemas and deterministic risk classification policies (`LOW`, `MEDIUM`, `HIGH`).
   - Safety restrictions: Simulated-only execution boundaries; zero direct cluster mutation permitted.

#### Concrete Demo Input Example:
- **Scenario**: Payment service begins returning HTTP 500 errors during a controlled `http_500_spike` fault-injection experiment (`FAULT-1D8A4DA5`, `error_rate: 1.0`).
- **Telemetry Fed**: Prometheus records 100% error rate (0/10 OK, 10/10 500s); Loki captures error stack traces; Jaeger isolates 7 failed spans (`EV-TRACE-3F77AC`).
- **Context Fed**: Incident ID `INC-CD90E2`, active fault change metadata (`EV-CHANGE-9964BD`), pod health (`EV-INFRA-5B1A7A`), and 3 pgvector runbooks (`EVID-KNOW-6750`).

---

## Slide 8: Project Output: What Does SentryOps Produce?
### Root Cause Diagnosis, Remediation Proposals, Safety Decisions & Verification Outcomes

```text
  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────┐
  │  Diagnosis   │ ──► │  Remediation │ ──► │ 🛡 Human Approval Gate│
  │  (RCA Proof) │     │   Proposal   │     │ (Mandatory for Med/Hi)│
  └──────────────┘     └──────────────┘     └──────────┬───────────┘
    [ APPROVED ] ──► Simulated Exec ──► Verification Checks ──► RESOLVED
    [ REJECTED ] ──► Action Cancelled (null) ──► Stays in INVESTIGATING
```

#### Four Output Categories:
1. **A. Incident Diagnosis & Root Cause Analysis (RCA)**:
   - Affected service attribution (`payment-service`), root cause classification, and confidence score.
   - Evidence linkage: Cross-correlated telemetry evidence (`EV-TRACE-3F77AC`, `EV-CHANGE-9964BD`, `EV-INFRA-5B1A7A`).
   - Anti-Hallucination verification: Validated that all cited evidence IDs exist in ground truth store.
2. **B. Structured Remediation Proposal**:
   - Allowlisted action proposal: `SCALE_SERVICE` for target `payment-service`.
   - Validated parameters: `replicas: 2` (plainly labeled `[DEMO FIXTURE - MOCK_LLM]`).
   - Deterministic risk assessment: Classified as `MEDIUM` risk flagging mandatory human approval requirement.
3. **C. Safety Decision & Execution Result**:
   - Approval audit status: `APPROVED` or `REJECTED` recorded with decision metadata.
   - Execution status: `SUCCESS` applied strictly against in-memory `SIMULATED_INFRA_STATE`.
   - Hardened cluster boundary: Zero live Kubernetes mutations (`kubectl get deployment` remains at 1 replica).
4. **D. Deterministic Verification & Postmortem**:
   - Automated post-remediation verification checks: `replica_count` (2) and `service_health` (healthy) passed (`VERIFIED_SUCCESS`).
   - Lifecycle resolution: Incident marked `RESOLVED` (or remains `INVESTIGATING` if rejected).
   - Structured postmortem: 9-section postmortem generated deterministically; evaluation pass across 4 dimensions.

#### Concrete Demo Output & Recovery Lifecycle:
- **Diagnosis & Proposal**: RCA diagnosed payment-service failure. Proposed `SCALE_SERVICE` (replicas: 2), rated `MEDIUM` risk (`PENDING_APPROVAL`).
- **Approval Path (`INC-CD90E2`)**: Operator approved (`POST /approve`) ➔ status `APPROVED` ➔ updated simulated state (`SUCCESS`) ➔ verified healthy ➔ status `RESOLVED`.
- **Rejection Path (`INC-28EE86`)**: Operator rejected (`POST /reject`) ➔ status `REJECTED` ➔ execution cancelled (`null`) ➔ verification skipped ➔ remains `INVESTIGATING`.
- **Simulated vs Real Actuation**: Remediation executor updated in-memory simulated state only. Live cluster deployment (`payment-service`) remained strictly at 1 replica.
- **Actual Live Recovery Truth**: Live HTTP traffic recovered (10/10 OK, 1.051s latency) strictly following explicit fault cleanup (`POST /cleanup`), NOT from simulated scaling.

---

## Slide 9: Observable Telemetry & Operator Dashboard
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

## Slide 10: Live Demonstration Walkthrough
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

## Slide 11: Execution, Verification & Postmortem
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

## Slide 12: Technical Testing & Metric Disclosure
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

## Slide 13: Security Architecture & Operational Boundaries
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

## Slide 14: Summary & Future Roadmap
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
