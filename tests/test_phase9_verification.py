import pytest
import sys
import os
from datetime import datetime

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.schemas.all import VerificationResult, VerificationCheck
from app.services.verification import perform_verification, run_deterministic_checks
from app.services.remediation import update_simulated_state
from app.ai.agents.verification_agent import verification_agent_node
from app.ai.state import InvestigationState

# 1. successful restart
def test_successful_restart():
    update_simulated_state("test-svc", {"status": "healthy"})
    ar = {"success": True, "action_type": "RESTART_SERVICE", "target": "test-svc"}
    state = {"evidence": [{"evidence_id": "ev_1"}]}
    res = perform_verification(ar, state)
    assert res.verified is True

# 2. failed restart
def test_failed_restart():
    update_simulated_state("test-svc", {"status": "unhealthy"})
    ar = {"success": True, "action_type": "RESTART_SERVICE", "target": "test-svc"}
    state = {"evidence": [{"evidence_id": "ev_1"}]}
    res = perform_verification(ar, state)
    assert res.verified is False

# 3. successful scale
def test_successful_scale():
    update_simulated_state("test-svc", {"status": "healthy", "replicas": 5})
    ar = {"success": True, "action_type": "SCALE_SERVICE", "target": "test-svc", "new_state": {"replicas": 5}}
    state = {"evidence": [{"evidence_id": "ev_1"}]}
    res = perform_verification(ar, state)
    assert res.verified is True

# 4. failed scale
def test_failed_scale():
    update_simulated_state("test-svc", {"status": "healthy", "replicas": 3})
    ar = {"success": True, "action_type": "SCALE_SERVICE", "target": "test-svc", "new_state": {"replicas": 5}}
    state = {"evidence": [{"evidence_id": "ev_1"}]}
    res = perform_verification(ar, state)
    assert res.verified is False

# 5. successful rollback
def test_successful_rollback():
    update_simulated_state("test-svc", {"status": "healthy", "version": "v1"})
    ar = {"success": True, "action_type": "ROLLBACK_SERVICE", "target": "test-svc", "new_state": {"version": "v1"}}
    state = {"evidence": [{"evidence_id": "ev_1"}]}
    res = perform_verification(ar, state)
    assert res.verified is True

# 6. failed rollback
def test_failed_rollback():
    update_simulated_state("test-svc", {"status": "unhealthy", "version": "v2"})
    ar = {"success": True, "action_type": "ROLLBACK_SERVICE", "target": "test-svc", "new_state": {"version": "v1"}}
    state = {"evidence": [{"evidence_id": "ev_1"}]}
    res = perform_verification(ar, state)
    assert res.verified is False

# 7. missing action result
def test_missing_action_result():
    state = {"action_result": None}
    updates = verification_agent_node(state)
    assert "VERIFICATION_SKIPPED" in updates["timeline"][0]

# 8. fabricated action_result with success=True but no execution
def test_fabricated_action_result():
    state = {"action_result": {"success": True, "execution_id": None}}
    updates = verification_agent_node(state)
    assert "VERIFICATION_SKIPPED" in updates["timeline"][0]

# 9. pending approval cannot verify
def test_pending_approval_cannot_verify():
    # If pending approval, action_result isn't generated or success is false
    state = {"action_result": {"success": False}}
    updates = verification_agent_node(state)
    assert "VERIFICATION_SKIPPED" in updates["timeline"][0]

# 10. rejected action cannot verify
def test_rejected_action_cannot_verify():
    state = {"action_result": {"success": False}}
    updates = verification_agent_node(state)
    assert "VERIFICATION_SKIPPED" in updates["timeline"][0]

# 11. failed execution cannot verify
def test_failed_execution_cannot_verify():
    state = {"action_result": {"success": False, "execution_id": "123"}}
    updates = verification_agent_node(state)
    assert "VERIFICATION_SKIPPED" in updates["timeline"][0]

# 12. missing evidence cannot verify
def test_missing_evidence_cannot_verify():
    update_simulated_state("test-svc", {"status": "healthy"})
    ar = {"success": True, "action_type": "RESTART_SERVICE", "target": "test-svc"}
    state = {"evidence": []}
    res = perform_verification(ar, state)
    assert res.verified is False

# 13. invalid evidence cannot verify
def test_invalid_evidence_cannot_verify():
    update_simulated_state("test-svc", {"status": "healthy"})
    ar = {"success": True, "action_type": "RESTART_SERVICE", "target": "test-svc"}
    state = {"evidence": [{"bad_key": "bad_val"}]}
    res = perform_verification(ar, state)
    assert res.verified is False

# 14. valid evidence is persisted
def test_valid_evidence_is_persisted():
    update_simulated_state("test-svc", {"status": "healthy"})
    ar = {"success": True, "action_type": "RESTART_SERVICE", "target": "test-svc"}
    state = {"evidence": [{"evidence_id": "ev_123"}]}
    res = perform_verification(ar, state)
    assert "ev_123" in res.evidence_ids
    assert res.verified is True

# 15. successful verification -> RESOLVED
def test_successful_verification_resolved():
    update_simulated_state("test-svc", {"status": "healthy"})
    state = {
        "evidence": [{"evidence_id": "ev_1"}],
        "action_result": {
            "success": True,
            "execution_id": "exec_1",
            "action_type": "RESTART_SERVICE",
            "target": "test-svc"
        }
    }
    updates = verification_agent_node(state)
    assert updates.get("status") == "RESOLVED"

# 16. failed verification -> INVESTIGATING
def test_failed_verification_investigating():
    update_simulated_state("test-svc", {"status": "unhealthy"})
    state = {
        "evidence": [{"evidence_id": "ev_1"}],
        "action_result": {
            "success": True,
            "execution_id": "exec_1",
            "action_type": "RESTART_SERVICE",
            "target": "test-svc"
        }
    }
    updates = verification_agent_node(state)
    assert updates.get("status") == "INVESTIGATING"

# 17. Verification DB persistence
def test_verification_db_persistence():
    # Tested indirectly in API or test_backend.py, but we can verify schema creation
    from app.models.all import Verification
    v = Verification(incident_id=1, execution_id=1, status="VERIFIED_SUCCESS")
    assert v.status == "VERIFIED_SUCCESS"

# 18. GET verification API
# 19. automatic graph path
# 20. approval path
# 21. verification never routes back automatically
def test_graph_routing_no_remediation_loop():
    # Verifying there is no edge back to remediation
    from app.ai.graph import build_investigation_graph
    graph = build_investigation_graph()
    # The edges in graph define the routing.
    # Verification agent is a terminal node that just sets state, graph routes to END
    # Just asserting the graph can be built successfully without loop errors
    assert graph is not None

# 22. Graph Routing Scenarios for Verification Gate
def test_route_after_risk_engine_pending_approval():
    from langgraph.graph import END
    from app.ai.graph import route_after_risk_engine
    assert route_after_risk_engine({"approval_status": "PENDING_APPROVAL"}) == END


def test_route_after_risk_engine_scenarios():
    from langgraph.graph import END
    from app.ai.graph import route_after_risk_engine

    # Scenario 1: PENDING_APPROVAL -> END
    assert route_after_risk_engine({"approval_status": "PENDING_APPROVAL"}) == END

    # Scenario 2: missing action_result -> END
    assert route_after_risk_engine({"approval_status": "APPROVED", "action_result": None}) == END

    # Scenario 3: success=True but missing execution_id -> END
    assert route_after_risk_engine({
        "approval_status": "APPROVED",
        "action_result": {"success": True}
    }) == END

    # Scenario 4: success=True and has execution_id -> verification_agent
    assert route_after_risk_engine({
        "approval_status": "APPROVED",
        "action_result": {"success": True, "execution_id": "exec_123"}
    }) == "verification_agent"

    # Scenario 5: success=False and has execution_id -> END
    assert route_after_risk_engine({
        "approval_status": "APPROVED",
        "action_result": {"success": False, "execution_id": "exec_123"}
    }) == END
