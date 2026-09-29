# SentryOps Project Status

Autonomous Multi-Agent Production Incident Response and Root Cause Analysis Platform.

## Executive Status Summary

| Phase | Title | Status | Primary Artifacts |
|---|---|---|---|
| **Phase 0** | Foundation & Repository Setup | Completed | Project structure, Docker Compose, Env config |
| **Phase 1** | Microservices Architecture | Completed | Order, Payment, Notification, User services, API Gateway |
| **Phase 2** | Observability Infrastructure | Completed | OpenTelemetry, Prometheus, Loki, Jaeger |
| **Phase 3** | Fault Injection Framework | Completed | Simulated faults (`fault-injection` service on port 8005) |
| **Phase 4** | Incident Management Backend | Completed | PostgreSQL, SQLAlchemy models, Incident REST API |
| **Phase 5** | Initial AI Agent Orchestration | Completed | LangGraph pipeline (IncidentManager, Log, Metrics, RCA) |
| **Phase 6** | Advanced Multi-Agent Investigation | Completed | TraceAgent, DeploymentAgent, InfrastructureAgent, Fan-out/Fan-in |
| **Phase 7** | Knowledge Base & RAG | Completed | pgvector, KnowledgeAgent, chunking, Runbook/Postmortem retrieval |
| **Phase 8** | Remediation & Risk Engine | Completed | RemediationProposal, deterministic Risk Engine, Approval workflow |
| **Phase 9** | Verification Agent | Completed | Post-action verification, deterministic checks, state transition |
| **Phase 10** | Operator Dashboard / UI | Completed | React 19, TypeScript, Vite, responsive SRE incident UI |
| **Phase 11** | Incident Evaluation Framework | Completed | Deterministic 4-dimension evaluation, API & UI integration |
| **Phase 12** | Incident Replay & Postmortems | Completed | Read-only deterministic replay, structured postmortem, API & UI integration |
| **Phase 13** | Kubernetes Deployment | Completed | `k8s/` manifests, dedicated namespace, StatefulSet+PVC database, probes, local-cluster docs |

---

## Complete Incident Lifecycle

SentryOps now implements the complete observable lifecycle:

```text
DETECTION
    ↓
INVESTIGATION (Log, Metrics, Trace, Deployment, Infrastructure, Knowledge Agents)
    ↓
EVIDENCE COLLECTION (Structured, linked, validated telemetry)
    ↓
RCA (Evidence-grounded root-cause analysis)
    ↓
REMEDIATION PROPOSAL (Strict allowlist: RESTART, SCALE, ROLLBACK)
    ↓
RISK ASSESSMENT (Deterministic policy rules: LOW, MEDIUM, HIGH)
    ↓
HUMAN APPROVAL (Pause gate for Medium/High risk actions)
    ↓
EXECUTION (Controlled execution tools against simulated production state)
    ↓
VERIFICATION (Deterministic post-remediation health & state checks)
    ↓
EVALUATION (Deterministic quality, completeness, and consistency evaluation)
```

---

## Phase 11 — Incident Evaluation Framework Details

### Purpose
The Evaluation Framework evaluates the completed incident-response lifecycle. It is **not** an execution controller; it evaluates whether the incident was investigated effectively, whether root causes are grounded in evidence, whether remediation respected safety policies, and whether recovery was verified.

### Evaluation Dimensions & Deterministic Checks

1. **Investigation Evaluation**:
   - `investigation.started`: Verifies that investigation was started or completed.
   - `evidence.available`: Verifies that at least 1 evidence item was collected.
   - `evidence.quality`: Checks that all collected evidence contains valid summary and payload data.
   - `investigation.agents_successful`: Verifies that all agent execution records completed without errors.
   - *Result*: `PASS`, `PARTIAL`, `FAIL`, or `NOT_EVALUABLE`.

2. **RCA Evaluation**:
   - `rca.exists`: Verifies the generation of a RootCause record.
   - `rca.content_valid`: Verifies that the root cause description is non-empty.
   - `rca.confidence_valid`: Checks that confidence is within `[0.0, 1.0]`.
   - `rca.evidence_linked`: Strictly validates that referenced evidence IDs exist in the incident's collected evidence.
   - *Result*: `PASS`, `PARTIAL`, `FAIL`, or `NOT_EVALUABLE`.

3. **Remediation Evaluation**:
   - `remediation.exists`: Verifies the presence of a RemediationProposal.
   - `remediation.action_valid`: Confirms action belongs to the allowlist (`RESTART_SERVICE`, `SCALE_SERVICE`, `ROLLBACK_SERVICE`).
   - `remediation.target_service`: Verifies target service is explicitly specified.
   - `remediation.risk_assessed`: Verifies deterministic risk assessment with valid risk level.
   - `remediation.approval_respected`: Confirms that actions requiring approval were approved prior to execution (and no executions occurred on pending/rejected proposals).
   - `remediation.execution_result`: Checks that controlled execution succeeded where expected.
   - *Result*: `PASS`, `PARTIAL`, `FAIL`, or `NOT_EVALUABLE`.

4. **Verification Evaluation**:
   - `verification.exists`: Verifies post-execution verification execution.
   - `verification.checks_present`: Checks that individual verification checks were performed.
   - `verification.checks_outcome`: Evaluates pass/fail outcome across all verification checks.
   - `verification.status_consistent`: Confirms verification status aligns with check outcomes.
   - `verification.incident_status_aligned`: Verifies incident transitioned to `RESOLVED` on verification success, or `INVESTIGATING` (re-investigation) on failure.
   - *Result*: `PASS`, `PARTIAL`, `FAIL`, or `NOT_EVALUABLE`.

### Overall Status Aggregation
- **PASS**: All 4 dimensions evaluated to `PASS`.
- **PARTIAL**: Non-critical warnings, mixed check outcomes, or stages awaiting approval/execution.
- **FAIL**: Any critical failure (e.g. missing evidence, hallucinated RCA links, failed execution, failed verification).
- **NOT_EVALUABLE**: Lifecycle has not progressed sufficiently (e.g. initial `DETECTED` status).

### Failures & Actionable Recommendations
- Every failing check is aggregated with observed vs expected details.
- Contextual, actionable recommendations are generated for operators (e.g., verifying telemetry collectors, reviewing pending approvals, or triggering re-investigation).

---

## Phase 12 — Incident Replay & Postmortems Details

### Purpose
Phase 12 turns a completed incident into a reproducible historical artifact. It reconstructs the incident lifecycle from persisted records, re-runs the deterministic analysis, compares the result against what was recorded, and assembles a structured postmortem. It is entirely read-only.

### Replay (`app/services/replay.py`)
- Collects the persisted lifecycle via the shared read-only collector `app/services/history.py`.
- Reconstructs stages: incident, evidence, investigation, RCA, remediation, risk, approval, execution, verification, evaluation.
- Re-runs deterministic analysis: risk policy (`evaluate_risk`) and evaluation (`evaluate_incident(..., persist=False)`).
- Emits `IncidentReplayResult` with `replay_consistency` of `MATCH`, `MISMATCH`, or `INCOMPLETE`, plus an explicit original-vs-replay `differences` list.
- Recorded remediation actions are exposed only as `historical_actions`; they are never executed.

### Postmortem (`app/services/postmortem.py`)
- Deterministically assembled from persisted data with no LLM required for correctness.
- Sections: DETECTION, INVESTIGATION, EVIDENCE, ROOT_CAUSE, REMEDIATION, APPROVAL, EXECUTION, VERIFICATION, EVALUATION, plus a top-level summary, impact, timeline, and lessons/recommendations.
- The timeline uses only persisted timestamps; entries lacking a timestamp are reported honestly (`timestamp=None`) and sorted last rather than fabricated.

### Safety Boundaries
1. Replay and postmortem never execute remediation (`RESTART_SERVICE`, `SCALE_SERVICE`, `ROLLBACK_SERVICE`) — historical actions are treated as data only.
2. No infrastructure access or mutation: no Docker/Kubernetes/AWS/shell/SSH, and simulated infrastructure state is untouched.
3. No database writes: both services only read persisted records.

### API Endpoints
- `GET /incidents/{incident_id}/replay`: read-only deterministic replay result.
- `GET /incidents/{incident_id}/postmortem`: read-only deterministic postmortem document.

---

## Phase 13 — Kubernetes Deployment Details

### Purpose
Phase 13 makes SentryOps deployable to a **local** Kubernetes cluster (Minikube, kind, or Docker Desktop Kubernetes) while preserving the existing application architecture. It is deployment infrastructure only — not autonomous Kubernetes remediation. Full guide: `docs/kubernetes.md`.

### Workloads (namespace `sentryops`)
| Kind | Workloads |
|---|---|
| StatefulSet | `postgres` (pgvector, StatefulSet + `volumeClaimTemplates` PVC) |
| Deployment | `redis`, `backend`, `frontend` |
| Deployment | `api-gateway`, `order-service`, `payment-service`, `notification-service`, `user-service`, `fault-injection` |
| Deployment | `prometheus`, `loki`, `jaeger`, `grafana` |

### Configuration
- `sentryops-config`: shared non-secret values (`POSTGRES_*`, `REDIS_URL`).
- `backend-config`: `LOKI_URL` (query base), `PROMETHEUS_URL`, `JAEGER_URL`, `FAULT_API_URL`, `MOCK_LLM`.
- `microservices-config`: `LOKI_URL` (**push** URL), `OTLP_ENDPOINT`, downstream service URLs.
- `sentryops-secrets`: `POSTGRES_PASSWORD`, `DATABASE_URL` (documented local-dev placeholders).
- `LOKI_URL` deliberately differs between the backend and the microservices (query base vs push endpoint).

### Storage, Networking, Health
- PostgreSQL persists via `volumeClaimTemplates` (2Gi RWO); Redis and the observability stack use `emptyDir` (documented limitation).
- ClusterIP for all internal services; only the frontend is exposed (`NodePort 30080`). nginx reverse-proxies `/api` to `backend:8000`, so the browser stays same-origin and no CORS change was required.
- Readiness and liveness probes reuse the existing `/health` endpoints; the backend also has a startup probe. Dependency ordering uses init containers that poll readiness instead of `depends_on` or blind sleeps.

### Deployment Commands
```bash
scripts/k8s-build-images.sh   # build + load the eight application images (no registry)
scripts/k8s-deploy.sh         # namespace + observability ConfigMaps + kubectl apply -k k8s/
```

### Safety Boundaries
1. **No RBAC objects**: no Role, RoleBinding, ClusterRole, ClusterRoleBinding or ServiceAccount is created; nothing references `cluster-admin`.
2. **No cluster credentials in containers**: every application pod sets `automountServiceAccountToken: false`.
3. **No kubectl from workloads**: no image, command or argument invokes `kubectl` or a Kubernetes client; no privileged containers, `hostPath` or `hostNetwork`.
4. **Remediation boundary unchanged**: the allow-list → risk → approval → controlled action → verification chain is untouched. `LLM → kubectl` is explicitly not implemented.

---

## Safety Boundaries

1. **No Infrastructure Commands**: The evaluator cannot execute shell commands or infrastructure actions.
2. **No Approval Modification**: The evaluator cannot approve or reject remediation proposals.
3. **No Production State Mutation**: The evaluator cannot modify simulated or real production states.
4. **Read-Only & Deterministic**: The evaluator computes evaluation results using deterministic rules directly from persisted state.
5. **No LLM in Critical Path**: Safety decisions are never delegated to unconstrained LLMs.

---

## API Endpoints

- `GET /incidents/{incident_id}/evaluation`: Deterministically computes and returns structured `EvaluationResult`.
- `GET /incidents/{incident_id}/replay`: Read-only deterministic incident replay (`IncidentReplayResult`).
- `GET /incidents/{incident_id}/postmortem`: Read-only deterministic postmortem (`PostmortemResult`).
- `GET /incidents`: List incidents with status and severity filters.
- `GET /incidents/{incident_id}`: Incident details.
- `GET /incidents/{incident_id}/timeline`: Chronological event log.
- `GET /incidents/{incident_id}/evidence`: Collected telemetry evidence.
- `GET /incidents/{incident_id}/rca`: Root cause analysis and evidence linkage.
- `GET /incidents/{incident_id}/remediation`: Remediation proposal, approval, and execution status.
- `GET /incidents/{incident_id}/risk`: Deterministic risk evaluation.
- `GET /incidents/{incident_id}/verification`: Verification status and checks.
- `POST /incidents/{incident_id}/approve`: Operator approval for pending remediation.
- `POST /incidents/{incident_id}/reject`: Operator rejection for pending remediation.
- `GET /service-health/{service}`: Real-time simulated service health.

---

## Testing & Verification Summary

- **Backend Unit Tests**:
  - `tests/test_phase11_evaluation.py`: 11 passed (100% coverage of required evaluation scenarios)
  - `tests/test_phase9_verification.py`: 20 passed
  - `tests/test_phase8_remediation.py`: 7 passed
  - `tests/test_phase7_knowledge_agent.py`: 1 passed
  - `tests/test_phase7_knowledge.py` (unit): 4 passed
  - `tests/test_phase6_investigation.py` (agents): 8 passed
- **Frontend Verification**:
  - Linting (`oxlint`): 0 errors
  - Type checking (`tsc -b`): 0 errors
  - Production build (`vite build`): Succeeded (dist output generated cleanly)
- **Phase 12 Tests**:
  - `tests/test_phase12_replay_postmortem.py`: 19 passed (replay consistency, deterministic replay, mismatch detection, read-only guarantees, historical-action safety, postmortem sections/timeline/no-fabrication, 404 handling)
- **Phase 13 Tests**:
  - `tests/test_phase13_kubernetes.py`: 84 passed (manifest/config/probe/persistence/security/regression assertions)
- **Whitespace / Git Checks**:
  - `git diff --check`: no whitespace errors
