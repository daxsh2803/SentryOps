import pytest
import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.schemas.all import RemediationProposal, RiskAssessment, ActionResult, ApprovalCreate
from app.models.all import Incident, IncidentStatus, Severity, Remediation, Approval, Execution, Verification, IncidentEvent
from app.ai.llm import get_llm, MockChatModel
from app.ai.agents.remediation_agent import remediation_agent_node
from app.ai.agents.risk_engine import risk_engine_node
from app.ai.agents.verification_agent import verification_agent_node
from app.ai.graph import graph, route_after_risk_engine
from app.services.remediation import (
    evaluate_risk,
    execute_controlled_action,
    get_simulated_state,
    update_simulated_state,
    SUPPORTED_ACTIONS,
    SIMULATED_INFRA_STATE,
)
from app.services.verification import perform_verification, run_deterministic_checks
from app.api.incidents import approve_remediation, reject_remediation


def test_mock_llm_produces_explicit_demo_fixture():
    """Verify MockChatModel generates a valid, supported, and clearly labeled demo proposal."""
    llm = get_llm()
    assert isinstance(llm, MockChatModel), "Expected MockChatModel under MOCK_LLM=true"

    state = {
        "incident_id": "INC-TEST-DEMO",
        "affected_service": "payment-service",
        "fault_type": "http_500_spike",
        "root_cause": "Database connection pool exhaustion",
        "root_cause_confidence": 0.9,
        "root_cause_evidence_ids": ["EV-001"],
        "evidence": [{"evidence_id": "EV-001", "summary": "High error rate"}],
    }

    updates = remediation_agent_node(state)
    assert "remediation_proposal" in updates
    proposal = updates["remediation_proposal"]

    # Must propose a supported action from allowlist
    assert proposal["action_type"] in SUPPORTED_ACTIONS
    assert proposal["action_type"] == "SCALE_SERVICE"
    assert proposal["target_service"] == "payment-service"
    assert proposal["parameters"] == {"replicas": 2}

    # Must be explicitly labeled as demo fixture to distinguish from live LLM output
    assert "[DEMO FIXTURE - MOCK_LLM]" in proposal["reason"]
    assert proposal["confidence"] == 0.9
    assert proposal["evidence_ids"] == ["EV-001"]


def test_crash_fault_produces_restart_demo_fixture():
    """Verify service_crash fault produces a RESTART_SERVICE fixture."""
    state = {
        "incident_id": "INC-CRASH-DEMO",
        "affected_service": "order-service",
        "fault_type": "service_crash",
        "evidence": [{"evidence_id": "EV-CRASH-01"}],
    }
    updates = remediation_agent_node(state)
    proposal = updates["remediation_proposal"]

    assert proposal["action_type"] == "RESTART_SERVICE"
    assert proposal["target_service"] == "order-service"
    assert proposal["parameters"] == {"instances": "multiple"}
    assert "[DEMO FIXTURE - MOCK_LLM]" in proposal["reason"]


def test_evidence_ids_exist_in_actual_collection_no_fabrication():
    """Verify proposal only references evidence IDs that exist in the actual incident collection."""
    # Case 1: Multiple real evidence items
    actual_evidence = [
        {"evidence_id": "EV-LOG-101", "summary": "HTTP 500 error in logs"},
        {"evidence_id": "EV-METRIC-202", "summary": "Latency p95 above 2000ms"},
        {"evidence_id": "EV-TRACE-303", "summary": "Database timeout trace"},
    ]
    state_with_evidence = {
        "incident_id": "INC-EVID-TEST",
        "affected_service": "payment-service",
        "fault_type": "http_500_spike",
        "evidence": actual_evidence,
    }
    updates = remediation_agent_node(state_with_evidence)
    proposal = updates["remediation_proposal"]

    actual_ids = {e["evidence_id"] for e in actual_evidence}
    assert len(proposal["evidence_ids"]) > 0
    for eid in proposal["evidence_ids"]:
        assert eid in actual_ids, f"Proposed evidence ID {eid} not in actual incident evidence collection!"

    # Case 2: Zero evidence in incident
    state_empty_evidence = {
        "incident_id": "INC-NO-EVID",
        "affected_service": "payment-service",
        "fault_type": "http_500_spike",
        "evidence": [],
    }
    updates_empty = remediation_agent_node(state_empty_evidence)
    assert updates_empty["remediation_proposal"]["evidence_ids"] == [], "Nonexistent evidence IDs were fabricated!"

    # Case 3: Simulated LLM hallucination of unknown IDs must be stripped
    with patch("app.ai.agents.remediation_agent.get_remediation_agent") as mock_get:
        mock_agent = MagicMock()
        mock_response = MagicMock()
        mock_response.content = """{
            "action_type": "SCALE_SERVICE",
            "target_service": "payment-service",
            "parameters": {"replicas": 2},
            "reason": "Test",
            "evidence_ids": ["EV-LOG-101", "EV-FABRICATED-999"],
            "confidence": 0.9
        }"""
        mock_agent.invoke.return_value = mock_response
        mock_get.return_value = mock_agent

        updates_filtered = remediation_agent_node(state_with_evidence)
        proposal_filtered = updates_filtered["remediation_proposal"]
        assert "EV-LOG-101" in proposal_filtered["evidence_ids"]
        assert "EV-FABRICATED-999" not in proposal_filtered["evidence_ids"], "Hallucinated evidence ID was not filtered!"


def test_risk_engine_authoritative_gate():
    """Verify the deterministic risk engine gates the demo proposal at PENDING_APPROVAL without auto-execution."""
    proposal = RemediationProposal(
        action_type="SCALE_SERVICE",
        target_service="payment-service",
        parameters={"replicas": 2},
        reason="[DEMO FIXTURE - MOCK_LLM] Scale service to mitigate load",
        evidence_ids=["EV-001"],
        confidence=0.9,
    )

    risk = evaluate_risk(proposal)
    assert risk.risk_level == "MEDIUM"
    assert risk.allowed is True
    assert risk.requires_approval is True
    assert "SCALE_SERVICE requires strict validation and approval" in risk.reasons[0]

    state = {"remediation_proposal": proposal.model_dump()}
    updates = risk_engine_node(state)

    assert updates["approval_status"] == "PENDING_APPROVAL"
    assert "APPROVAL_REQUIRED" in updates["timeline"]
    # Critical safety assertion: action must NOT have been executed
    assert "action_result" not in updates
    # Critical router assertion: graph terminates at PENDING_APPROVAL
    assert route_after_risk_engine(updates) == "__end__"


def test_safety_boundary_unsupported_and_malformed_actions_rejected():
    """Verify unsupported commands or illegal parameters are strictly rejected."""
    # 1. Arbitrary shell command or unsupported action
    malicious_proposal = RemediationProposal(
        action_type="EXECUTE_SHELL",
        target_service="payment-service",
        parameters={"command": "rm -rf /"},
        reason="Malicious or unconstrained prompt injection",
        evidence_ids=[],
        confidence=0.1,
    )
    risk = evaluate_risk(malicious_proposal)
    assert risk.risk_level == "HIGH"
    assert risk.allowed is False
    assert risk.requires_approval is True
    assert "Unsupported action type: EXECUTE_SHELL" in risk.reasons[0]

    # 2. Malformed parameters (replicas > 5)
    excessive_proposal = RemediationProposal(
        action_type="SCALE_SERVICE",
        target_service="payment-service",
        parameters={"replicas": 100},
        reason="Excessive scaling",
        evidence_ids=[],
        confidence=0.5,
    )
    risk = evaluate_risk(excessive_proposal)
    assert risk.risk_level == "HIGH"
    assert risk.allowed is False
    assert "Invalid or excessive replica count" in risk.reasons[0]

    # 3. High risk rollback
    rollback_proposal = RemediationProposal(
        action_type="ROLLBACK_SERVICE",
        target_service="payment-service",
        parameters={"version": "v1.0.0"},
        reason="Rollback",
        evidence_ids=[],
        confidence=0.8,
    )
    risk = evaluate_risk(rollback_proposal)
    assert risk.risk_level == "HIGH"
    assert risk.allowed is False
    assert "ROLLBACK_SERVICE always requires human approval" in risk.reasons[0]


def test_controlled_execution_against_simulated_infrastructure():
    """Verify execution occurs purely in the simulated environment without host operations."""
    service = "payment-service"
    update_simulated_state(service, {"status": "unhealthy", "replicas": 1})

    proposal = RemediationProposal(
        action_type="SCALE_SERVICE",
        target_service=service,
        parameters={"replicas": 2},
        reason="[DEMO FIXTURE - MOCK_LLM] Scale service",
        evidence_ids=["EV-001"],
        confidence=0.9,
    )

    action_res = execute_controlled_action(proposal)
    assert action_res.success is True
    assert action_res.action_type == "SCALE_SERVICE"
    assert action_res.target == service
    assert action_res.execution_id is not None

    # Check simulated state was updated
    sim_state = get_simulated_state(service)
    assert sim_state["replicas"] == 2
    assert sim_state["status"] == "healthy"


def test_verification_agent_deterministic_workflow():
    """Verify verification agent validates simulated recovery and resolves the incident."""
    service = "payment-service"
    update_simulated_state(service, {"status": "healthy", "replicas": 2})

    action_res_dict = {
        "success": True,
        "execution_id": "exec-demo-12345",
        "action_type": "SCALE_SERVICE",
        "target": service,
        "new_state": {"replicas": 2, "status": "healthy"},
        "message": f"Successfully scaled service {service} to 2 replicas",
        "timestamp": datetime.utcnow().isoformat(),
    }

    state = {
        "action_result": action_res_dict,
        "evidence": [{"evidence_id": "EV-001", "summary": "Payment error rate"}],
    }

    updates = verification_agent_node(state)
    assert "verification_result" in updates
    verif = updates["verification_result"]
    assert verif["verified"] is True
    assert verif["verification_status"] == "VERIFIED_SUCCESS"
    assert updates["status"] == "RESOLVED"
    assert "INCIDENT_RESOLVED" in updates["timeline"]


def test_approval_endpoint_unit_flow_with_mock_db():
    """Verify /incidents/{id}/approve processes pending approvals, executes safely, and resolves incident."""
    # Setup mock incident, remediation, approval
    mock_db = MagicMock()
    inc = Incident(
        id=1,
        incident_id="INC-APP-001",
        title="Payment 500 spike",
        status=IncidentStatus.INVESTIGATING,
        severity=Severity.HIGH,
        affected_service="payment-service"
    )
    rem = Remediation(
        id=10,
        incident_id=1,
        action_type="SCALE_SERVICE",
        description="[DEMO FIXTURE - MOCK_LLM] Scale service",
        status="PENDING_APPROVAL",
        parameters={"replicas": 2, "target_service": "payment-service"}
    )
    appr = Approval(
        id=20,
        incident_id=1,
        remediation_id=10,
        status="PENDING"
    )

    def query_mock(model):
        q = MagicMock()
        if model == Incident:
            q.filter.return_value.first.return_value = inc
        elif model == Approval:
            q.filter.return_value.first.return_value = appr
        elif model == Remediation:
            q.filter.return_value.first.return_value = rem
        return q

    mock_db.query.side_effect = query_mock

    # Test approve endpoint
    res = approve_remediation("INC-APP-001", ApprovalCreate(reason="LGTM after review"), db=mock_db)
    assert res["status"] == "APPROVED"
    assert res["execution_status"] == "SUCCESS"
    assert appr.status == "APPROVED"
    assert inc.status == "RESOLVED"
    assert mock_db.commit.called

    # Test approving when no pending approval exists raises 404
    mock_db_none = MagicMock()
    def query_mock_none(model):
        q = MagicMock()
        if model == Incident:
            q.filter.return_value.first.return_value = inc
        elif model == Approval:
            q.filter.return_value.first.return_value = None
        return q
    mock_db_none.query.side_effect = query_mock_none

    with pytest.raises(HTTPException) as exc_info:
        approve_remediation("INC-APP-001", ApprovalCreate(reason="Retry"), db=mock_db_none)
    assert exc_info.value.status_code == 404
    assert "No pending approval found" in exc_info.value.detail


def test_reject_remediation_endpoint():
    """Verify /incidents/{id}/reject marks approval REJECTED without executing action."""
    mock_db = MagicMock()
    inc = Incident(id=2, incident_id="INC-REJ-002", title="Test", status=IncidentStatus.INVESTIGATING, severity=Severity.HIGH)
    rem = Remediation(id=11, incident_id=2, action_type="SCALE_SERVICE", description="Demo", status="PENDING_APPROVAL", parameters={})
    appr = Approval(id=21, incident_id=2, remediation_id=11, status="PENDING")

    def query_mock(model):
        q = MagicMock()
        if model == Incident:
            q.filter.return_value.first.return_value = inc
        elif model == Approval:
            q.filter.return_value.first.return_value = appr
        return q
    mock_db.query.side_effect = query_mock

    res = reject_remediation("INC-REJ-002", ApprovalCreate(reason="Too high risk"), db=mock_db)
    assert res["status"] == "REJECTED"
    assert appr.status == "REJECTED"
    assert appr.reason == "Too high risk"
    # Action was NOT executed, incident status not RESOLVED
    assert inc.status == IncidentStatus.INVESTIGATING
    assert mock_db.commit.called


def test_full_investigation_to_approval_lifecycle():
    """Demonstrate end-to-end: investigation -> proposal -> risk gate -> simulated execution -> verification."""
    # Reset simulated state
    service = "payment-service"
    update_simulated_state(service, {"status": "unhealthy", "replicas": 1})

    initial_state = {
        "incident_id": "INC-E2E-DEMO",
        "db_incident_id": 99,
        "status": "INVESTIGATING",
        "severity": "HIGH",
        "affected_service": service,
        "fault_type": "http_500_spike",
        "incident_context": "Elevated 500 errors on payment endpoints",
        "investigation_plan": "",
        "log_findings": [],
        "metric_findings": [],
        "trace_findings": [],
        "deployment_findings": [],
        "infrastructure_findings": [],
        "knowledge_findings": [],
        "evidence": [{"evidence_id": "EV-TRACE-99", "summary": "500 Internal Server Error"}],
        "root_cause": "",
        "root_cause_confidence": 0.0,
        "root_cause_evidence_ids": [],
        "errors": [],
        "timeline": ["AI_INVESTIGATION_STARTED"],
    }

    # Step 1: Run graph
    investigation_state = graph.invoke(initial_state)

    # Verify RCA and proposal
    assert investigation_state["root_cause"] != ""
    assert "remediation_proposal" in investigation_state
    proposal_dict = investigation_state["remediation_proposal"]
    assert proposal_dict["action_type"] == "SCALE_SERVICE"
    assert proposal_dict["target_service"] == service
    assert "[DEMO FIXTURE - MOCK_LLM]" in proposal_dict["reason"]

    # Verify every evidence ID in proposal exists in incident evidence
    for eid in proposal_dict["evidence_ids"]:
        assert eid in [e["evidence_id"] for e in investigation_state["evidence"]]

    # Verify safety gate: halted at PENDING_APPROVAL
    assert investigation_state["approval_status"] == "PENDING_APPROVAL"
    assert "action_result" not in investigation_state
    assert "verification_result" not in investigation_state

    # Step 2: Human Operator approves the proposal
    proposal = RemediationProposal(**proposal_dict)
    risk = evaluate_risk(proposal)
    assert risk.allowed is True
    assert risk.requires_approval is True

    # Controlled execution
    action_result = execute_controlled_action(proposal)
    assert action_result.success is True

    # Step 3: Deterministic verification
    verif_state = {
        "action_result": action_result.model_dump(),
        "evidence": investigation_state["evidence"],
    }
    verif_updates = verification_agent_node(verif_state)

    assert verif_updates["status"] == "RESOLVED"
    assert verif_updates["verification_result"]["verified"] is True
    assert "INCIDENT_RESOLVED" in verif_updates["timeline"]
