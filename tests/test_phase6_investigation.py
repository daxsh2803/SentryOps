import sys
import os
import pytest
import httpx
from unittest.mock import patch, MagicMock

# Ensure backend directory is in python path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.ai.state import InvestigationState
from app.ai.agents.trace_agent import trace_agent_node, parse_jaeger_traces
from app.ai.agents.deployment_agent import deployment_agent_node
from app.ai.agents.infrastructure_agent import infrastructure_agent_node
from app.ai.agents.rca_agent import rca_agent_node
from app.ai.graph import graph

BACKEND_API = "http://127.0.0.1:8080"

# --- 1. TraceAgent Tests ---

def test_trace_agent_success():
    sample_jaeger_data = {
        "data": [
            {
                "traceID": "trace-101",
                "processes": {
                    "p1": {"serviceName": "payment-service"}
                },
                "spans": [
                    {
                        "traceID": "trace-101",
                        "spanID": "span-root",
                        "operationName": "POST /pay",
                        "startTime": 1690000000000000,
                        "duration": 120000,
                        "processID": "p1",
                        "tags": [
                            {"key": "http.status_code", "value": 500},
                            {"key": "error", "value": True}
                        ]
                    },
                    {
                        "traceID": "trace-101",
                        "spanID": "span-child",
                        "operationName": "db.query",
                        "startTime": 1690000000050000,
                        "duration": 50000,
                        "processID": "p1",
                        "references": [
                            {"refType": "CHILD_OF", "spanID": "span-root"}
                        ],
                        "tags": [
                            {"key": "error", "value": True},
                            {"key": "error.message", "value": "connection refused"}
                        ]
                    }
                ]
            }
        ]
    }
    
    with patch("httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = sample_jaeger_data
        mock_get.return_value = mock_resp
        
        state: InvestigationState = {"affected_service": "payment-service"}
        result = trace_agent_node(state)
        
        assert "trace_findings" in result
        findings = result["trace_findings"]
        assert len(findings) == 1
        assert findings[0]["status"] == "traces_found"
        assert findings[0]["total_traces"] == 1
        assert findings[0]["error_traces_count"] == 1
        
        # Verify span extraction
        trace_info = findings[0]["traces"][0]
        assert trace_info["trace_id"] == "trace-101"
        assert len(trace_info["spans"]) == 2
        root_span = trace_info["spans"][0]
        assert root_span["span_id"] == "span-root"
        assert root_span["operation"] == "POST /pay"
        assert root_span["http_status"] == 500
        assert root_span["is_error"] is True
        
        child_span = trace_info["spans"][1]
        assert child_span["parent_span_id"] == "span-root"
        assert child_span["error_message"] == "connection refused"
        
        # Verify evidence
        assert len(result["evidence"]) == 1
        ev = result["evidence"][0]
        assert ev["evidence_type"] == "TRACE"
        assert ev["source"] == "jaeger"
        assert ev["service"] == "payment-service"
        assert "timestamp" in ev
        assert "traces" in ev["payload"]
        assert "AGENT_COMPLETED: TraceAgent" in result["timeline"]

def test_trace_agent_graceful_failure():
    with patch("httpx.get", side_effect=Exception("Jaeger timeout")):
        state: InvestigationState = {"affected_service": "payment-service"}
        result = trace_agent_node(state)
        assert len(result["errors"]) >= 1
        assert "TraceAgent Error" in result["errors"][0]
        assert "AGENT_COMPLETED: TraceAgent" in result["timeline"]

def test_trace_agent_no_traces():
    with patch("httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": []}
        mock_get.return_value = mock_resp
        
        state: InvestigationState = {"affected_service": "payment-service"}
        result = trace_agent_node(state)
        assert result["trace_findings"][0]["status"] == "no_traces_found"
        assert len(result["evidence"]) == 0

# --- 2. DeploymentAgent Tests ---

def test_deployment_agent_active_synthetic_fault():
    sample_faults = [
        {
            "fault_id": "flt-123",
            "fault_type": "artificial_latency",
            "target_service": "payment-service",
            "status": "ACTIVE",
            "injected_at": "2026-09-26T12:00:00Z"
        }
    ]
    with patch("httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = sample_faults
        mock_get.return_value = mock_resp
        
        state: InvestigationState = {"affected_service": "payment-service"}
        result = deployment_agent_node(state)
        
        # Verify deployment metadata availability explicit flag
        findings = result["deployment_findings"]
        assert findings[0]["deployment_metadata_available"] is False
        assert findings[0]["status"] == "deployment_metadata_unavailable"
        
        # Verify active synthetic faults found and clearly labeled
        assert findings[1]["status"] == "synthetic_faults_found"
        assert findings[1]["synthetic_faults_count"] == 1
        
        # Verify evidence does not claim to be a real deployment
        assert len(result["evidence"]) == 1
        ev = result["evidence"][0]
        assert ev["evidence_type"] == "CHANGE"
        assert ev["source"] == "synthetic-fault-injection"
        assert "Synthetic fault injection active" in ev["summary"]
        assert ev["timestamp"] == "2026-09-26T12:00:00Z"

def test_deployment_agent_no_active_faults():
    with patch("httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []
        mock_get.return_value = mock_resp
        
        state: InvestigationState = {"affected_service": "payment-service"}
        result = deployment_agent_node(state)
        
        findings = result["deployment_findings"]
        assert findings[0]["deployment_metadata_available"] is False
        assert findings[1]["status"] == "no_synthetic_faults_found"
        assert len(result["evidence"]) == 0

# --- 3. InfrastructureAgent Tests ---

def test_infrastructure_agent_success():
    sample_prometheus_data = {
        "data": {
            "result": [
                {
                    "metric": {"job": "payment-service", "instance": "127.0.0.1:8002"},
                    "value": [1690000000, "1"]
                }
            ]
        }
    }
    with patch("httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = sample_prometheus_data
        mock_get.return_value = mock_resp
        
        state: InvestigationState = {"affected_service": "payment-service"}
        result = infrastructure_agent_node(state)
        
        assert len(result["infrastructure_findings"]) == 1
        assert result["infrastructure_findings"][0]["status"] == "infrastructure_checked"
        assert len(result["evidence"]) == 1
        ev = result["evidence"][0]
        assert ev["evidence_type"] == "INFRASTRUCTURE"
        assert ev["source"] == "prometheus"
        assert "timestamp" in ev

def test_infrastructure_agent_failure():
    with patch("httpx.get", side_effect=Exception("Prometheus unavailable")):
        state: InvestigationState = {"affected_service": "payment-service"}
        result = infrastructure_agent_node(state)
        assert len(result["errors"]) >= 1
        assert "InfrastructureAgent Error" in result["errors"][0]

# --- 4. RCA Agent Evidence ID Filtering Tests ---

def test_rca_agent_filters_hallucinated_evidence_ids():
    state: InvestigationState = {
        "incident_id": "INC-TEST-1",
        "affected_service": "payment-service",
        "evidence": [
            {"evidence_id": "EV-TRACE-001", "summary": "Error trace"},
            {"evidence_id": "EV-CHANGE-002", "summary": "Synthetic fault"}
        ],
        "trace_findings": [],
        "deployment_findings": [],
        "infrastructure_findings": []
    }
    
    # LLM hallucinates an ID: "EV-HALLUCINATED-999" along with a valid ID
    mock_llm_output = MagicMock()
    mock_llm_output.content = '{"root_cause": "Latency Spike", "confidence": 0.95, "evidence_ids": ["EV-TRACE-001", "EV-HALLUCINATED-999"]}'
    
    with patch("app.ai.agents.rca_agent.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_llm_output
        mock_get_llm.return_value = mock_llm
        
        result = rca_agent_node(state)
        assert result["root_cause"] == "Latency Spike"
        assert "EV-TRACE-001" in result["root_cause_evidence_ids"]
        # Crucial check: Hallucinated ID must be filtered out!
        assert "EV-HALLUCINATED-999" not in result["root_cause_evidence_ids"]
        assert len(result["root_cause_evidence_ids"]) == 1

def test_rca_agent_fallback_when_all_ids_hallucinated():
    state: InvestigationState = {
        "incident_id": "INC-TEST-2",
        "affected_service": "payment-service",
        "evidence": [
            {"evidence_id": "EV-VALID-100", "summary": "Real evidence"}
        ],
        "trace_findings": [],
        "deployment_findings": [],
        "infrastructure_findings": []
    }
    
    # LLM returns ONLY fake IDs
    mock_llm_output = MagicMock()
    mock_llm_output.content = '{"root_cause": "Crash", "confidence": 0.8, "evidence_ids": ["FAKE-1", "FAKE-2"]}'
    
    with patch("app.ai.agents.rca_agent.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_llm_output
        mock_get_llm.return_value = mock_llm
        
        result = rca_agent_node(state)
        # Should fallback safely to collected IDs
        assert "EV-VALID-100" in result["root_cause_evidence_ids"]
        assert "FAKE-1" not in result["root_cause_evidence_ids"]

# --- 5. LangGraph Parallel Execution & State Consistency ---

def test_langgraph_parallel_execution_and_findings():
    initial_state = {
        "incident_id": "INC-GRAPH-TEST",
        "db_incident_id": 1,
        "status": "DETECTED",
        "severity": "HIGH",
        "affected_service": "payment-service",
        "fault_type": "artificial_latency",
        "incident_context": "Testing parallel fan-out/fan-in",
        "investigation_plan": "",
        "log_findings": [],
        "metric_findings": [],
        "trace_findings": [],
        "deployment_findings": [],
        "infrastructure_findings": [],
        "evidence": [],
        "root_cause": "",
        "root_cause_confidence": 0.0,
        "root_cause_evidence_ids": [],
        "errors": [],
        "timeline": ["START"]
    }
    
    # Execute compiled LangGraph
    final_state = graph.invoke(initial_state)
    
    # Verify fan-out occurred: timeline contains start and completion for all 5 agents
    timeline_str = " ".join(final_state["timeline"])
    assert "LogAgent" in timeline_str
    assert "MetricsAgent" in timeline_str
    assert "TraceAgent" in timeline_str
    assert "DeploymentAgent" in timeline_str
    assert "InfrastructureAgent" in timeline_str
    assert "RCAAgent" in timeline_str
    
    # Verify all 5 agent finding fields populated in final state
    assert isinstance(final_state["log_findings"], list)
    assert isinstance(final_state["metric_findings"], list)
    assert isinstance(final_state["trace_findings"], list)
    assert isinstance(final_state["deployment_findings"], list)
    assert isinstance(final_state["infrastructure_findings"], list)
    
    # Verify RCA ran after the 5 agents
    assert final_state["root_cause"] != ""

# --- 6. End-to-End Persistence Integration Test ---

def test_phase6_backend_e2e_persistence():
    # 1. Create incident via Backend API
    payload = {
        "title": "Phase 6 Full Investigation Incident",
        "description": "Validating Phase 6 agent execution tracking and evidence persistence",
        "severity": "CRITICAL",
        "affected_service": "payment-service",
        "fault_type": "http_500_spike"
    }
    r = httpx.post(f"{BACKEND_API}/incidents", json=payload)
    assert r.status_code == 200, r.text
    incident = r.json()
    inc_id = incident["incident_id"]

    # 2. Trigger AI Investigation
    r = httpx.post(f"{BACKEND_API}/incidents/{inc_id}/ai-investigate")
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["status"] == "INVESTIGATING"

    # 3. Verify AgentExecution records for all 7 Phase 6 agents
    r = httpx.get(f"{BACKEND_API}/incidents/{inc_id}/executions")
    assert r.status_code == 200, r.text
    executions = r.json()
    executed_agents = [e["agent_name"] for e in executions]
    
    expected_agents = [
        "IncidentManager",
        "LogAgent",
        "MetricsAgent",
        "TraceAgent",
        "DeploymentAgent",
        "InfrastructureAgent",
        "RCAAgent"
    ]
    for agent in expected_agents:
        assert agent in executed_agents, f"Expected agent {agent} in executed agents: {executed_agents}"

    # 4. Verify Timeline persistence
    r = httpx.get(f"{BACKEND_API}/incidents/{inc_id}/timeline")
    assert r.status_code == 200, r.text
    timeline = r.json()
    event_types = [t["event_type"] for t in timeline]
    assert "AI_INVESTIGATION_STARTED" in event_types
    assert "AI_INVESTIGATION_COMPLETED" in event_types
    assert "AGENT_STARTED" in event_types
    assert "AGENT_COMPLETED" in event_types

    # 5. Verify Evidence persistence with timestamps
    r = httpx.get(f"{BACKEND_API}/incidents/{inc_id}/evidence")
    assert r.status_code == 200, r.text
    evidence_list = r.json()
    for ev in evidence_list:
        assert "evidence_id" in ev
        assert "evidence_type" in ev
        assert "timestamp" in ev
