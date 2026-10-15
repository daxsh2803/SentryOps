# SentryOps

> **Autonomous Multi-Agent Production Incident Response & Root Cause Analysis Platform**
> *Course: CSE311 Artificial Intelligence | Final Project Review*
> *Author / Contributor: Daksh Singh*
> *GitHub Repository: [https://github.com/daxsh2803/SentryOps](https://github.com/daxsh2803/SentryOps)*

---

## Table of Contents
- [1. Project Title](#1-project-title)
- [2. Introduction](#2-introduction)
  - [Problem Addressed](#problem-addressed)
  - [Objective](#objective)
  - [Relevance & Operational Impact](#relevance--operational-impact)
- [3. Methodology](#3-methodology)
  - [System Architecture & End-to-End Workflow](#system-architecture--end-to-end-workflow)
  - [Multi-Agent LangGraph Orchestration & Specialized Roles](#multi-agent-langgraph-orchestration--specialized-roles)
  - [Observability Pipeline: Prometheus, Loki & Jaeger](#observability-pipeline-prometheus-loki--jaeger)
  - [Fault Injection Control Center & Supported Anomaly Scenarios](#fault-injection-control-center--supported-anomaly-scenarios)
  - [Deterministic Risk Policy & Human-in-the-Loop Safety Gate](#deterministic-risk-policy--human-in-the-loop-safety-gate)
  - [Actuation Boundary, Automated Verification & Audit Reporting](#actuation-boundary-automated-verification--audit-reporting)
- [4. Results](#4-results)
  - [Implemented Capabilities & Demonstrated Features](#implemented-capabilities--demonstrated-features)
  - [Verified Fault-Injection & Recovery Walkthrough (`INC-CD90E2`)](#verified-fault-injection--recovery-walkthrough-inc-cd90e2)
  - [Quality Assurance & Test Suite Results](#quality-assurance--test-suite-results)
  - [Observability Dashboard & Application Evidence](#observability-dashboard--application-evidence)
- [5. Conclusion](#5-conclusion)
  - [Work Completed](#work-completed)
  - [Main Outcome & Value Demonstrated](#main-outcome--value-demonstrated)
  - [Operational Limitations & Implementation Boundaries](#operational-limitations--implementation-boundaries)
- [6. References](#6-references)
- [Detailed Technical Documentation & Runbook](#detailed-technical-documentation--runbook)
  - [Prerequisites](#prerequisites)
  - [Local Cluster & Stack Deployment](#local-cluster--stack-deployment)
  - [Local Development & Port Forwarding](#local-development--port-forwarding)
  - [Environment Variables](#environment-variables)
  - [Reproducing the Demonstration Workflow](#reproducing-the-demonstration-workflow)
  - [Backend & Microservice API Reference](#backend--microservice-api-reference)
  - [Phased Architecture History](#phased-architecture-history)

---

## 1. Project Title

- **Project Name**: SentryOps
- **Tagline**: An AI-assisted Site Reliability Engineering (SRE) incident investigation and response platform combining multi-agent telemetry synthesis, deterministic safety boundaries, and human-in-the-loop remediation.
- **Repository**: [https://github.com/daxsh2803/SentryOps](https://github.com/daxsh2803/SentryOps)
- **Academic Context**: CSE311 Artificial Intelligence | Final Project Review
- **Author / Contributor**: Daksh Singh ([@daxsh2803](https://github.com/daxsh2803))

---

## 2. Introduction

### Problem Addressed
Modern microservice architectures deployed on Kubernetes generate immense volumes of telemetry across distributed boundaries. During high-severity production outages, site reliability engineers (SREs) face acute cognitive overload: they must manually query Prometheus metrics, grep through Loki logs, trace distributed spans in Jaeger, inspect Kubernetes pod statuses, and cross-reference internal wikis or runbooks. This fragmented manual correlation introduces high Mean Time to Detect (MTTD) and Mean Time to Remediate (MTTR), while increasing the risk of misdiagnosis or flawed remediation commands executed under high operational stress.

### Objective
SentryOps demonstrates an end-to-end, structured incident response workflow that combines:
1. **Automated Telemetry Aggregation**: Simultaneous collection of error logs, latency/error metrics, distributed traces, and infrastructure state.
2. **Coordinated Multi-Agent Investigation**: A LangGraph orchestration pipeline deploying specialized investigation agents that run in parallel.
3. **Evidence-Linked Root Cause Analysis (RCA)**: Synthesizing telemetry findings with anti-hallucination validation against verified incident evidence IDs.
4. **Risk-Aware Remediation Proposals**: Strict allow-listed operational actions evaluated by an immutable, deterministic (non-LLM) risk policy engine.
5. **Human Approval & Actuation Boundary**: A mandatory human-in-the-loop gate for medium/high-risk actions, executing against an isolated in-memory simulation state rather than mutating production deployments.
6. **Automated Verification & Auditable Reporting**: Closed-loop post-action verification, full lifecycle state replay, and automated executive report generation (Markdown & standalone HTML).

### Relevance & Operational Impact
Providing AI assistance to SREs requires unwavering safety. Completely unconstrained autonomous agents risk executing destructive commands or compounding cluster instability. SentryOps tackles this challenge by decoupling cognitive synthesis (handled by parallel AI agents) from operational execution (governed by hardcoded deterministic rules, human approval gates, and strict simulation boundaries). This ensures faster, evidence-backed, fully auditable incident resolution without relinquishing operational control.

---

## 3. Methodology

### System Architecture & End-to-End Workflow

The SentryOps platform is structured into three primary tiers: the simulated microservice ecosystem, the observability stack, and the SentryOps multi-agent backend and operator dashboard.

```text
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │                      KUBERNETES APPLICATION WORKLOADS (:8080 / :8005)                  │
 │                                                                                        │
 │    User / Demo Traffic ──► [API Gateway :8080]                                         │
 │                                  │                                                     │
 │                 ┌────────────────┼────────────────┐                                    │
 │                 ▼                ▼                ▼                                    │
 │          [Order Service]  [Payment Service]  [Inventory Service]                       │
 │                 │                │                │                                    │
 │                 └────────────────┼────────────────┘                                    │
 │                                  ▼                                                     │
 │                         [Notification Service]                                         │
 │                                  ▲                                                     │
 │                                  │ Synthetic Anomaly Injection                         │
 │                    [Fault Injection API :8005]                                         │
 └──────────────────────────────────┬─────────────────────────────────────────────────────┘
                                    │ Emits Metrics, Logs & Distributed Traces
                                    ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │                    OBSERVABILITY & TELEMETRY INFRASTRUCTURE                            │
 │   • Prometheus (:9090): HTTP rates, error percentages, CPU/memory telemetry            │
 │   • Grafana Loki (:3100): Structured JSON application logs & error stack traces        │
 │   • Jaeger (:16686): OpenTelemetry distributed trace spans & parent-child relationships │
 │   • Grafana (:3000): Unified operational telemetry dashboard                           │
 └──────────────────────────────────┬─────────────────────────────────────────────────────┘
                                    │ Telemetry Polling & Query APIs
                                    ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
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
 │  │  • Lifecycle Audit: Replay Reconstruction & Structured Postmortem Generator      │  │
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

### Multi-Agent LangGraph Orchestration & Specialized Roles

The core investigation engine uses **LangGraph** to coordinate parallel telemetry collection and convergence:

```mermaid
graph TD
    A[Incident Triggered] --> B[Incident Manager Node]
    B --> C[Log Agent - Loki]
    B --> D[Metrics Agent - Prometheus]
    B --> E[Trace Agent - Jaeger]
    B --> F[Deployment Agent - Fault API]
    B --> G[Infrastructure Agent - Pod Telemetry]
    B --> H[Knowledge Agent - pgvector RAG]
    C --> I[RCA Agent - Evidence Synthesis]
    D --> I
    E --> I
    F --> I
    G --> I
    H --> I
    I --> J[Remediation Agent]
    J --> K{Deterministic Risk Policy Engine}
    K -- "MEDIUM / HIGH Risk" --> L[PENDING_APPROVAL: Wait for Human Operator]
    L -- "Operator Approved" --> M[In-Memory Executor]
    K -- "LOW Risk" --> M
    M --> N[Verification Agent]
    N --> O[Incident Resolved / Re-investigate]
```

1. **Incident Manager**: Coordinates state initialization and fans out parallel queries across all observability modalities.
2. **Log Agent**: Queries Loki for application error logs, matching service names and time bounds around the incident start.
3. **Metrics Agent**: Queries Prometheus PromQL endpoints to detect HTTP 5xx error spikes and p99 latency regressions.
4. **Trace Agent**: Queries Jaeger distributed tracing APIs to isolate failing HTTP spans and client-server dependency breakdowns.
5. **Deployment Agent**: Inspects active fault injection state and deployment configuration changes.
6. **Infrastructure Agent**: Collects pod restart counts, resource quotas, and node health signals.
7. **Knowledge Agent (RAG)**: Executes vector cosine similarity search over historical incident postmortems and runbooks stored in PostgreSQL using `pgvector`.
8. **RCA Agent**: Performs fan-in synthesis of all collected evidence. Validates that every conclusion links to an authentic evidence ID (`EV-*`) recorded in the database, preventing hallucinated root causes.
9. **Remediation Agent**: Maps identified root causes to a parameterized action from a strict allowlist.

### Observability Pipeline: Prometheus, Loki & Jaeger
- **Prometheus (`:9090`)**: Scrapes `/metrics` endpoints across all services every 5 seconds, calculating error ratios (`rate(http_requests_total{status=~"5.."}[1m])`).
- **Grafana Loki (`:3100`)**: Ingests structured JSON logs tagged by service, level, and trace ID.
- **Jaeger (`:16686`)**: Captures end-to-end OpenTelemetry spans spanning `api-gateway` -> `order-service` -> `payment-service`.

### Fault Injection Control Center & Supported Anomaly Scenarios
SentryOps includes an integrated Fault Injection Control Center (`frontend/src/pages/FaultInjection.tsx`) communicating with the `fault-injection` microservice (`:8005`):
- `http_500_spike`: Forces a target service to return HTTP 500 responses at a configurable rate (e.g., 80%).
- `high_latency`: Injects artificial delay (e.g., 2000ms) into downstream HTTP request handlers.
- `service_down`: Simulates complete service unresponsiveness or termination.
- `database_connection_pool_exhaustion`: Artificially exhausts mock database pool connections.
- `cpu_stress`: Saturates CPU utilization within the container environment.

### Deterministic Risk Policy & Human-in-the-Loop Safety Gate
To prevent dangerous operations, remediation risk evaluation is completely decoupled from LLM inference:
- **Allowlisted Actions**: Only `RESTART_SERVICE`, `SCALE_SERVICE`, and `ROLLBACK_SERVICE` are valid actions. Unrecognized action types are rejected immediately.
- **Deterministic Policy Table**:
  - `RESTART_SERVICE`: Classified as `LOW` risk (restarts a stateless pod; permitted to execute autonomously or via policy).
  - `SCALE_SERVICE`: Classified as `MEDIUM` risk (changes workload allocation; halts at `PENDING_APPROVAL` requiring human operator confirmation).
  - `ROLLBACK_SERVICE`: Classified as `HIGH` risk (alters service version; halts at `PENDING_APPROVAL` requiring human operator confirmation).
  - `UNKNOWN` / arbitrary commands: Hard rejected as `UNSAFE`.

### Actuation Boundary, Automated Verification & Audit Reporting
- **In-Memory Actuation Boundary**: The remediation executor applies actions against an in-memory `SIMULATED_INFRA_STATE` dictionary. It deliberately makes **zero live cluster mutations** (`kubectl` commands are not executed against the live cluster), ensuring the platform remains safe for evaluation and learning.
- **Automated Verification Agent**: Following remediation execution, the verification agent checks replica state and validates that error rates have normalized before marking the incident status as `RESOLVED`.
- **Audit Reporting Engine (`reportGenerator.ts`)**: Generates comprehensive incident postmortems exportable directly from the UI as:
  - **Markdown (`.md`)**: Formatted for GitHub, Jira, or engineering wikis.
  - **Standalone Executive HTML (`.html`)**: Self-contained, responsive report complete with embedded CSS, severity badges, timeline graphs, evidence tables, risk analysis, and audit trails.

---

## 4. Results

### Implemented Capabilities & Demonstrated Features
- **Deterministic Incident Timeline & Timestamp Serialization**: All backend models serialize timestamps in timezone-aware UTC ISO 8601 with trailing `'Z'` (`serialize_utc_datetime`). Incident lists sort newest-first deterministically with primary key tie-breaking.
- **Integrated Operator Dashboard**: React + Vite frontend providing real-time incident browsing, severity filters, automated refresh, AI investigation triggering, and one-click report export.
- **Fault Injection Control Center**: UI enabling operators to inject and clear faults on demand, run order traffic simulations, and inspect gateway responses.
- **Lifecycle Audit & Evaluation**: Structured postmortems capturing timeline events, evidence correlation, remediation actions, and verification outcomes.

### Verified Fault-Injection & Recovery Walkthrough (`INC-CD90E2`)
A complete end-to-end lifecycle demonstration was verified using `demo_runner.py` targeting the `payment-service`:

```text
Baseline (10/10 OK) ──► Fault Active (0/10 OK, 10/10 500s) ──► Fault Cleared ──► Recovery Verified (10/10 OK)
```

1. **Baseline Phase**: Generated 10 requests to `POST /orders` via `api-gateway` (`:8080`). All 10 requests succeeded (0% error rate).
2. **Fault Injection Phase**: Injected `http_500_spike` into `payment-service` with `error_rate: 0.8`. Success rate dropped to 0% (10/10 failed with HTTP 500).
3. **Incident Creation & AI Investigation**: Incident `INC-CD90E2` created. Multi-agent investigation collected logs (`EV-LOG-421738`), metrics (`EV-METRIC-23A54C`), traces (`EV-TRACE-3F77AC`), and fault state (`EV-CHANGE-9964BD`).
4. **RCA & Remediation Proposal**: The RCA agent identified the HTTP 500 spike. The remediation agent proposed `SCALE_SERVICE` (ID: 21). The deterministic risk policy classified it as `MEDIUM` risk, placing it in `PENDING_APPROVAL`.
5. **Operator Approval & Verification**: Approved via operator dashboard. Action executed against `SIMULATED_INFRA_STATE`. Fault cleared via `POST /faults/FAULT-1D8A4DA5/cleanup`.
6. **Recovery Verification**: Order traffic resumed at 100% success rate (10/10 succeeded, 0% error rate).

### Quality Assurance & Test Suite Results

Test execution was performed and verified across unit, integration, and platform test suites:

#### Targeted Unit & Modernization Suites (Today's Work)
| Test Suite | Command | Result | Scope Verified |
| :--- | :--- | :--- | :--- |
| **Backend Timestamp Serialization** | `pytest tests/test_incident_timestamps.py` | **8 / 8 PASSED (100%)** | UTC 'Z' ISO serialization, model field serializers, SQL query sorting |
| **Frontend Date Handling & Comparator** | `node --experimental-strip-types --test tests/test_frontend_date.mjs` | **7 / 7 PASSED (100%)** | Timestamp parsing, naive UTC normalization, tie-break ordering |
| **Executive Report Generator** | `node --experimental-strip-types --test tests/test_report_generator.mjs` | **2 / 2 PASSED (100%)** | Markdown & standalone HTML report generation across complete/partial incidents |
| **Frontend Production Build** | `npm run build` (`tsc -b && vite build`) | **SUCCESS (0 errors)** | 1,953 modules transformed, TypeScript compilation clean |

#### Targeted Kubernetes & Subsystem Test Suites
Across the targeted subsystem suites, **152 out of 152 tests passed (100%)**:
- `test_phase13_kubernetes.py`: **22 / 22 passed** (Cluster service routing, health endpoints, ingress)
- `test_phase12_replay_postmortem.py`: **27 / 27 passed** (Deterministic replay, postmortem schema)
- `test_phase11_evaluation.py`: **15 / 15 passed** (Evidence linkage validation, anti-hallucination checks)
- `test_phase9_verification.py`: **11 / 11 passed** (Closed-loop remediation verification)
- `test_phase8_workflow_demo.py`: **17 / 17 passed** (End-to-end incident lifecycle workflow)
- `test_phase8_remediation.py`: **12 / 12 passed** (Risk policy classification, allowlists)
- `test_phase7_knowledge.py`: **10 / 10 passed** (pgvector embeddings, runbook semantic search)
- `test_phase6_investigation.py`: **20 / 20 passed** (LangGraph fan-out, parallel agent execution)
- `test_services.py`: **10 / 10 passed** (FastAPI microservice endpoints)
- `test_fault_injection.py`: **8 / 8 passed** (Fault injection lifecycle and cleanup)

*Note on Legacy Integration Tests*: Legacy test files from early phases (`tests/test_ai_agent.py` and `tests/test_backend.py`) reflect initial pre-LangGraph mock contracts prior to the multi-agent graph architecture and are distinguished from the 152 passing active subsystem tests.

### Observability Dashboard & Application Evidence

#### 1. Operator Incident Dashboard
![Main Dashboard](docs/images/screenshots/dashboard-overview.png)
*Figure 1: SentryOps Incident Management Dashboard displaying active incidents, severities, affected services, and real-time status tracking.*

#### 2. Prometheus & Grafana Service Metrics
![Service Metrics](docs/images/screenshots/grafana-service-metrics.png)
*Figure 2: Real-time telemetry in Grafana tracking HTTP request latency, error spikes, and throughput across the microservice cluster.*

#### 3. AI Multi-Agent Investigation View
![AI Investigation](docs/images/screenshots/ai-investigation.png)
*Figure 3: Detail view of an incident showing synthesized findings from parallel Log, Metrics, Trace, and Infrastructure agents.*

#### 4. Remediation Proposal & Human Approval Gate
![Remediation Approval](docs/images/screenshots/remediation-approval.png)
*Figure 4: Operator approval gate displaying proposed remediation, deterministic risk classification (MEDIUM), and require approval banner.*

#### 5. Verified Post-Recovery State
![Incident Recovery State](docs/images/screenshots/incident-recovery-state.png)
*Figure 5: Post-recovery verification confirming service health restored and incident status updated to RESOLVED.*

#### 6. Demonstration Traffic & Telemetry Metrics
| Request Success vs Failure | Error Rate Progression | Request Latency |
| :---: | :---: | :---: |
| ![Success vs Failure](docs/images/demo/success_failures.png) | ![Error Rate](docs/images/demo/error_rate.png) | ![Latency](docs/images/demo/latency.png) |
| *Traffic drops to 0% success during fault* | *Error rate spikes during fault, clears on recovery* | *Fast-failing 500s reduce average latency* |

---

## 5. Conclusion

### Work Completed
SentryOps demonstrates a complete, functional prototype of an AI-assisted SRE platform. The project successfully implements:
1. Microservice architecture on Kubernetes with 5 microservices and an integrated fault injector.
2. Full observability pipeline incorporating Prometheus, Grafana Loki, and Jaeger distributed tracing.
3. Multi-agent investigation orchestration powered by LangGraph with 6 specialized parallel agents.
4. Deterministic non-LLM risk evaluation engine enforcing hardcoded safety policies and human approval.
5. In-memory simulated actuation boundary ensuring zero accidental cluster disruptions.
6. Incident replay, automated closed-loop verification, and multi-format executive report generation.

### Main Outcome & Value Demonstrated
The primary achievement of SentryOps is proving that AI-assisted incident response can drastically accelerate root cause discovery without compromising operational stability. By enforcing a strict boundary between automated telemetry reasoning and deterministic actuation rules, the platform eliminates hallucinated remediations and prevents rogue autonomous modifications to critical infrastructure.

### Operational Limitations & Implementation Boundaries

To ensure complete academic and technical transparency, the following operational boundaries must be explicitly noted:
1. **Deterministic / Mock LLM Reasoning**: Under the demonstration configuration (`MOCK_LLM=true`), the system produces deterministic root-cause analyses and remediation proposals clearly labeled as `[DEMO FIXTURE - MOCK_LLM]`. It references real database evidence IDs but does not execute unconstrained live LLM generation.
2. **In-Memory Actuation Boundary**: The remediation execution engine updates an internal, in-memory state dictionary (`SIMULATED_INFRA_STATE`). It does **not** execute live `kubectl` scale or rollback commands against the Kubernetes cluster.
3. **Incident Creation Workflow**: In the demonstration frontend, incidents are initiated via the backend API upon operator trigger or test runner request following fault injection. Fully automated Prometheus Alertmanager webhook ingestion is not currently claimed.
4. **Security & Development Environment Scope**: The platform is an academic research prototype. Backend API endpoints omit enterprise-grade authentication/authorization (OAuth2/RBAC), default credentials are used (`sentryops:sentryops`), and the local Kind cluster metrics-server utilizes `--kubelet-insecure-tls`.
5. **Storage Persistence**: Observability backends (Prometheus, Loki) utilize `emptyDir` volumes in the local Kind configuration, which do not persist across cluster teardown.

---

## 6. References

### Repository
- SentryOps Source Repository: [https://github.com/daxsh2803/SentryOps](https://github.com/daxsh2803/SentryOps)

### Core Technologies & Official Documentation
1. **LangGraph**: Orchestration framework for stateful, multi-agent workflows. [https://langchain-ai.github.io/langgraph/](https://langchain-ai.github.io/langgraph/)
2. **FastAPI**: Modern, high-performance Python web framework for building APIs. [https://fastapi.tiangolo.com/](https://fastapi.tiangolo.com/)
3. **Prometheus**: Open-source systems monitoring and alerting toolkit. [https://prometheus.io/docs/](https://prometheus.io/docs/)
4. **Grafana Loki**: Horizontally-scalable, highly-available log aggregation system. [https://grafana.com/docs/loki/](https://grafana.com/docs/loki/)
5. **Jaeger**: Open-source, end-to-end distributed tracing. [https://www.jaegertracing.io/docs/](https://www.jaegertracing.io/docs/)
6. **React & Vite**: Frontend UI library and next-generation frontend tooling. [https://react.dev/](https://react.dev/) | [https://vite.dev/](https://vite.dev/)
7. **PostgreSQL & pgvector**: Vector similarity search extension for PostgreSQL. [https://github.com/pgvector/pgvector](https://github.com/pgvector/pgvector)
8. **Kubernetes & Kind**: Container orchestration and local Kubernetes clusters using Docker container nodes. [https://kubernetes.io/docs/](https://kubernetes.io/docs/) | [https://kind.sigs.k8s.io/](https://kind.sigs.k8s.io/)

---

# Detailed Technical Documentation & Runbook

## Prerequisites
- **Operating System**: Linux, macOS, or Windows 11 with WSL2 / PowerShell.
- **Docker**: Docker Desktop or Docker Engine (min 4 vCPUs, 8 GB RAM allocated).
- **Kubernetes**: `kind` (Kubernetes in Docker) or `kubectl` configured to a local cluster.
- **Python**: Version 3.10 to 3.13.
- **Node.js**: Version 18+ (tested on Node.js v22).

---

## Local Cluster & Stack Deployment

### 1. Build Container Images (Optional if building locally)
```bash
./scripts/k8s-build-images.sh
```

### 2. Deploy the Kubernetes Stack
```bash
./scripts/k8s-deploy.sh
```
*Deploys the `sentryops` namespace containing: Postgres (with pgvector), Redis, Prometheus, Loki, Jaeger, Grafana, API Gateway, Order Service, Payment Service, Inventory Service, Notification Service, Fault Injection API, Backend API, and Frontend.*

### 3. Teardown
```bash
kubectl delete namespace sentryops
```

---

## Local Development & Port Forwarding

If running services in local development mode or connecting to the cluster:

```bash
# API Gateway
kubectl port-forward -n sentryops svc/api-gateway 8080:8000

# SentryOps Backend API
kubectl port-forward -n sentryops svc/backend 8000:8000

# Fault Injection API
kubectl port-forward -n sentryops svc/fault-injection 8005:8005

# Observability Dashboards
kubectl port-forward -n sentryops svc/prometheus 9090:9090
kubectl port-forward -n sentryops svc/grafana 3000:3000
kubectl port-forward -n sentryops svc/jaeger 16686:16686
```

### Running the Frontend Locally
```bash
cd frontend
npm install
npm run dev
```
*The local Vite server runs at `http://localhost:5173` with preconfigured proxies to `:8000` (`/api`), `:8005` (`/faults-api`), and `:8080` (`/gateway-api`).*

---

## Environment Variables

Copy `.env.example` to `.env` when configuring the backend locally:

```env
# Database configuration
POSTGRES_USER=sentryops
POSTGRES_PASSWORD=sentryops
POSTGRES_DB=sentryops
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
DATABASE_URL=postgresql+psycopg2://sentryops:sentryops@localhost:5432/sentryops

# Redis cache
REDIS_URL=redis://localhost:6379/0

# LLM Mocking (true uses deterministic demonstration fixtures)
MOCK_LLM=true
```

---

## Reproducing the Demonstration Workflow

To execute the automated end-to-end validation script and regenerate demonstration charts:

```bash
# Run the end-to-end demonstration workflow
python demo_runner.py

# Regenerate demonstration charts in docs/images/demo/
python generate_charts.py
```

---

## Backend & Microservice API Reference

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/incidents` | `GET` | List all incidents, ordered newest-first by creation timestamp |
| `/incidents` | `POST` | Create a new incident record (`DETECTED` status) |
| `/incidents/{id}` | `GET` | Retrieve full incident details, timeline, and current state |
| `/incidents/{id}/ai-investigate` | `POST` | Trigger multi-agent LangGraph investigation pipeline |
| `/incidents/{id}/timeline` | `GET` | Fetch chronological audit events for the incident |
| `/incidents/{id}/evidence` | `GET` | Retrieve aggregated evidence items (`EV-*`) |
| `/incidents/{id}/root-cause` | `GET` | Retrieve synthesized root cause analysis |
| `/incidents/{id}/remediation` | `GET` | Retrieve proposed remediation action and risk level |
| `/incidents/{id}/approve` | `POST` | Operator approval to execute pending remediation action |
| `/incidents/{id}/reject` | `POST` | Operator rejection of proposed remediation action |
| `/incidents/{id}/replay` | `GET` | Reconstruct full lifecycle progression from database audit trail |
| `/incidents/{id}/postmortem` | `GET` | Generate structured 9-section postmortem document |
| `/faults` | `GET` | List active synthetic faults from Fault Injection API (`:8005`) |
| `/faults/types` | `GET` | List all supported fault types (`:8005`) |
| `/faults/inject` | `POST` | Inject a synthetic anomaly into target service (`:8005`) |
| `/faults/{fault_id}/cleanup`| `POST` | Clear active fault and restore normal service operation (`:8005`) |
| `/orders` | `POST` | Submit test order request through API Gateway (`:8080`) |

---

## Phased Architecture History

<details>
<summary>Click to expand phased development milestones</summary>

- **Phase 1 & 2: Microservice Core & Telemetry Foundations**: Initial deployment of 5 FastAPI services with OpenTelemetry instrumentation exporting to Prometheus, Loki, and Jaeger.
- **Phase 3: Fault Injection Control**: Dedicated `fault-injection` microservice with 5 supported fault types and dynamic lifecycle management.
- **Phase 4: Incident Backend & Relational Persistence**: PostgreSQL schema tracking incidents, events, evidence, root causes, remediations, approvals, executions, and verifications.
- **Phase 5 & 6: LangGraph Multi-Agent Orchestration**: State graph fanning out to parallel Log, Metrics, Trace, Deployment, Infrastructure, and Knowledge agents.
- **Phase 7: Knowledge Base & Vector RAG**: PostgreSQL `pgvector` semantic similarity search over historical incident postmortems.
- **Phase 8 & 9: Deterministic Remediation & Verification**: Strict action allowlists, deterministic non-LLM risk classification, and closed-loop verification.
- **Phase 10: Operator Dashboard**: Modern React + Vite web console with real-time incident browsing, AI investigation triggering, and fault injection control.
- **Phase 11 & 12: Replay Engine & Postmortems**: Deterministic lifecycle audit replay and comprehensive postmortem generation.
- **Phase 13: Local Kubernetes Integration**: Containerized deployment on Kind using Kustomize manifests.
- **Phase 14: Quality Hardening & Modernization**: Standardized UTC ISO 8601 'Z' timestamp serialization, deterministic sorting, executive Markdown/HTML report export engine, and test suite verification.
</details>
