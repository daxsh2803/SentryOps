import pytest
from unittest.mock import patch, MagicMock
import sys
import os

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.services.remediation import evaluate_risk, execute_controlled_action, SUPPORTED_ACTIONS
from app.schemas.all import RemediationProposal
from app.ai.agents.remediation_agent import remediation_agent_node
from app.ai.agents.risk_engine import risk_engine_node
from app.models.all import Incident, Remediation, Approval, Execution, IncidentEvent

def test_risk_engine_low_risk():
    proposal = RemediationProposal(
        action_type="RESTART_SERVICE",
        target_service="order-service",
        parameters={"instances": "one"},
        reason="Restart unhealthy instance",
        evidence_ids=["EVID-123"],
        confidence=0.9
    )
    risk = evaluate_risk(proposal)
    assert risk.risk_level == "LOW"
    assert risk.allowed == True
    assert risk.requires_approval == False

def test_risk_engine_medium_risk():
    proposal = RemediationProposal(
        action_type="SCALE_SERVICE",
        target_service="order-service",
        parameters={"replicas": 3},
        reason="Scale up due to load",
        evidence_ids=[],
        confidence=0.8
    )
    risk = evaluate_risk(proposal)
    assert risk.risk_level == "MEDIUM"
    assert risk.allowed == True
    assert risk.requires_approval == True

def test_risk_engine_high_risk():
    proposal = RemediationProposal(
        action_type="ROLLBACK_SERVICE",
        target_service="payment-service",
        parameters={"version": "v1.0.0"},
        reason="Bad deployment",
        evidence_ids=[],
        confidence=1.0
    )
    risk = evaluate_risk(proposal)
    assert risk.risk_level == "HIGH"
    assert risk.allowed == False
    assert risk.requires_approval == True

def test_allowlist_unknown_action():
    proposal = RemediationProposal(
        action_type="DELETE_DATABASE",
        target_service="db",
        parameters={},
        reason="Clear data",
        evidence_ids=[],
        confidence=0.5
    )
    risk = evaluate_risk(proposal)
    assert risk.allowed == False
    assert risk.requires_approval == True
    assert "Unsupported action type" in risk.reasons[0]

def test_controlled_tools():
    # Test restart
    res = execute_controlled_action(RemediationProposal(
        action_type="RESTART_SERVICE", target_service="api", parameters={}, reason="", evidence_ids=[], confidence=1.0
    ))
    assert res.success == True
    assert res.action_type == "RESTART_SERVICE"

    # Test scale
    res = execute_controlled_action(RemediationProposal(
        action_type="SCALE_SERVICE", target_service="api", parameters={"replicas": 2}, reason="", evidence_ids=[], confidence=1.0
    ))
    assert res.success == True
    assert res.action_type == "SCALE_SERVICE"
    assert res.new_state["replicas"] == 2

    # Test rollback
    res = execute_controlled_action(RemediationProposal(
        action_type="ROLLBACK_SERVICE", target_service="api", parameters={"version": "v1"}, reason="", evidence_ids=[], confidence=1.0
    ))
    assert res.success == True
    assert res.action_type == "ROLLBACK_SERVICE"

@patch("app.ai.agents.remediation_agent.get_remediation_agent")
def test_remediation_agent_node(mock_get_agent):
    mock_agent = MagicMock()

    mock_response = MagicMock()
    mock_response.content = '''```json
    {
        "action_type": "RESTART_SERVICE",
        "target_service": "order-service",
        "parameters": {"instances": "one"},
        "reason": "Test reason",
        "evidence_ids": ["EVID-1"],
        "confidence": 0.95
    }
    ```'''
    mock_agent.invoke.return_value = mock_response

    mock_get_agent.return_value = mock_agent

    state = {
        "evidence": [{"evidence_id": "EVID-1", "evidence_type": "LOG"}]
    }

    updates = remediation_agent_node(state)
    assert "remediation_proposal" in updates
    proposal = updates["remediation_proposal"]
    assert proposal["action_type"] == "RESTART_SERVICE"
    assert proposal["evidence_ids"] == ["EVID-1"]

def test_risk_engine_node_approval_flow():
    # HIGH risk requiring approval
    state = {
        "remediation_proposal": {
            "action_type": "ROLLBACK_SERVICE",
            "target_service": "api",
            "parameters": {},
            "reason": "Test",
            "evidence_ids": [],
            "confidence": 1.0
        }
    }
    updates = risk_engine_node(state)
    assert updates["approval_status"] == "PENDING_APPROVAL"
    assert "action_result" not in updates

    # LOW risk auto-approved
    state2 = {
        "remediation_proposal": {
            "action_type": "RESTART_SERVICE",
            "target_service": "api",
            "parameters": {"instances": "one"},
            "reason": "Test",
            "evidence_ids": [],
            "confidence": 1.0
        }
    }
    updates2 = risk_engine_node(state2)
    assert updates2["approval_status"] == "APPROVED"
    assert "action_result" in updates2
    assert updates2["action_result"]["success"] == True
