# SentryOps — Live Demonstration & Rehearsal Guide

This guide details the step-by-step walkthrough for demonstrating SentryOps to operators, stakeholders, and reviewers.

---

## 1. Environment & Port-Forwarding Setup

Ensure the Kubernetes cluster is running with workloads in the `sentryops` namespace.

```bash
# Verify pods are healthy
kubectl get pods -n sentryops

# Required Host Port-Forwards:
kubectl port-forward -n sentryops svc/api-gateway 8080:8000     # Simulated API Gateway
kubectl port-forward -n sentryops svc/backend 8000:8000         # FastAPI Incident Backend
kubectl port-forward -n sentryops svc/frontend 3080:80          # Operator Dashboard
kubectl port-forward -n sentryops svc/fault-injection 8005:8005 # Fault Injection API
kubectl port-forward -n sentryops svc/grafana 3000:3000         # Grafana Dashboards
kubectl port-forward -n sentryops svc/jaeger 16686:16686        # Jaeger Distributed Tracing
```

---

## 2. Demonstration Flow: Step-by-Step

### Stage 1: Baseline Health & Dashboard Overview
1. Navigate to the Frontend Dashboard: `http://localhost:3080`.
2. Observe the incident list showing historical records and simulated microservice health status badges.
3. Open Grafana at `http://localhost:3000/d/fea7bbb7-f983-4797-b258-7bcb52436430/sentryops-observability`:
   - Point out the 5 core panels: **Service Health Status** (all 5 services reporting HEALTHY in green), **Request Rate**, **Error Rate (5xx)** (baseline at 0), **P95 Latency**, and **Live Service Logs (Loki)**.
4. Execute 10 baseline HTTP order transactions through the API Gateway:
   ```bash
   # All 10 requests succeed (HTTP 200 OK, ~1.1s avg latency)
   curl -X POST http://localhost:8080/orders -H "Content-Type: application/json" -d '{"amount": 100}'
   ```

### Stage 2: Injecting Controlled Fault (`http_500_spike`)
1. Trigger an HTTP 500 spike fault on `payment-service`:
   ```bash
   curl -X POST http://localhost:8005/faults/inject -H "Content-Type: application/json" -d '{
     "fault_type": "http_500_spike",
     "target_service": "payment-service",
     "parameters": {"error_rate": 1.0}
   }'
   ```
2. Note the returned `fault_id` (e.g. `FAULT-1D8A4DA5`).
3. Re-run traffic through the API Gateway:
   - Observe that requests fail with `HTTP 500 Internal Server Error`.
   - Grafana **Error Rate (5xx)** panel spikes to indicate high failure rate.
4. Open Jaeger at `http://localhost:16686`:
   - Filter by service `payment-service` and tag `error=true`.
   - Inspect a failed trace (e.g. `d8bbe1085c65157cb2a184ae192187df`) showing HTTP 500 error tags on downstream spans.

### Stage 3: Multi-Agent AI Investigation
1. Create and trigger an investigation for the incident via the backend:
   ```bash
   # Incident created (e.g. INC-CD90E2)
   curl -X POST http://localhost:8000/incidents/INC-CD90E2/ai-investigate
   ```
2. Explain the parallel LangGraph fan-out:
   - LogAgent inspects Loki for errors.
   - TraceAgent harvests Jaeger trace IDs (`EV-TRACE-3F77AC`).
   - DeploymentAgent detects active synthetic fault metadata (`EV-CHANGE-9964BD`).
   - InfrastructureAgent inspects pod metrics (`EV-INFRA-5B1A7A`).
   - KnowledgeAgent retrieves historical postmortems from pgvector (`EVID-KNOW-6750`).
3. Point out the RCA fan-in synthesis linking genuine telemetry evidence without hallucinated IDs.

### Stage 4: Risk Gate & Pending Approval State
1. View the incident in the Dashboard: `http://localhost:3080/incidents/INC-CD90E2`.
2. Inspect the **Remediation & Risk** card:
   - Action proposed: `SCALE_SERVICE` for `payment-service` with `replicas: 2`.
   - Plainly labeled: `[DEMO FIXTURE - MOCK_LLM] Deterministic proposal for demonstration: Scale service replicas to 2 to alleviate traffic/latency load.`
   - Deterministic Risk Policy: Evaluated as `MEDIUM` risk because scaling requires operational review.
   - Human Gate: Status halts at `PENDING_APPROVAL` with **Approve Action** and **Reject** buttons visible.

### Stage 5: Operator Approval & Deterministic Verification
1. Click **Approve Action** (or call `POST /incidents/INC-CD90E2/approve`).
2. Show the immediate state transitions:
   - Approval: `APPROVED`.
   - Execution Result: `SUCCESS` (in-memory `SIMULATED_INFRA_STATE` updated to 2 replicas).
   - Verification Card: `VERIFIED_SUCCESS` (both `replica_count` and `service_health` checks marked as Passed).
   - Incident Status: Automatically transitioned to `RESOLVED`.
3. **Safety Verification in Terminal**:
   - Run `kubectl get deployment payment-service -n sentryops`.
   - Emphasize to the audience that **live Kubernetes replicas remain at 1**. No real mutating commands were run against the cluster.

### Stage 6: Rejection Alternative Path (Incident `INC-28EE86`)
1. Show a second incident (`INC-28EE86`) where the operator selected **Reject** (`POST /incidents/INC-28EE86/reject`).
2. Demonstrate that:
   - Approval is marked `REJECTED`.
   - Execution remains `null`.
   - Verification is skipped.
   - Incident remains in `INVESTIGATING` to allow alternative human triage.

### Stage 7: Traffic Recovery via Fault Cleanup
1. Clear the active synthetic fault:
   ```bash
   curl -X POST http://localhost:8005/faults/FAULT-1D8A4DA5/cleanup
   ```
2. Re-test order processing through the API Gateway:
   ```bash
   # All 10 requests succeed (HTTP 200 OK, ~1.05s avg latency)
   curl -X POST http://localhost:8080/orders -H "Content-Type: application/json" -d '{"amount": 100}'
   ```
3. Show Grafana Error Rate dropping back to 0.
4. Review the completed Postmortem section on the incident detail page, showing all 9 sections available with zero missing timestamps.

---

## 3. Key Takeaways for Reviewers

- **Zero Hallucination Risk**: RCA evidence IDs are validated against genuine collected evidence.
- **Deterministic Guardrails**: LLMs never choose risk levels or decide whether an action can execute autonomously.
- **Strict Infrastructure Safety**: The platform strictly prevents unauthorized cluster mutation; live recovery is separated from simulated remediation.
