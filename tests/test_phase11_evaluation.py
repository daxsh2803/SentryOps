import sys
import os
import pytest
from unittest.mock import MagicMock
from datetime import datetime
from fastapi import HTTPException

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.models.all import (
    Incident,
    IncidentStatus,
    Severity,
    IncidentEvent,
    Evidence,
    RootCause,
    Remediation,
    Approval,
    Execution,
    Verification,
    Evaluation
)
from app.services.evaluation import (
    evaluate_incident,
    evaluate_investigation,
    evaluate_rca,
    evaluate_remediation,
    evaluate_verification,
    get_incident_evaluation_by_id as get_incident_evaluation
)
from app.services.remediation import get_simulated_state, update_simulated_state


def create_mock_db(
    incident,
    events=None,
    evidence=None,
    agent_executions=None,
    root_cause=None,
    remediation=None,
    approval=None,
    execution=None,
    verification=None,
    existing_eval=None
):
    db = MagicMock()
    events = events or []
    evidence = evidence or []
    agent_executions = agent_executions or []

    def mock_query(model):
        query_mock = MagicMock()
        if model == Incident:
            filter_mock = MagicMock()
            filter_mock.first.return_value = incident
            query_mock.filter.return_value = filter_mock
        elif model == IncidentEvent:
            filter_mock = MagicMock()
            order_mock = MagicMock()
            order_mock.all.return_value = events
            filter_mock.order_by.return_value = order_mock
            query_mock.filter.return_value = filter_mock
        elif model == Evidence:
            filter_mock = MagicMock()
            filter_mock.all.return_value = evidence
            query_mock.filter.return_value = filter_mock
        elif model == RootCause:
            filter_mock = MagicMock()
            order_mock = MagicMock()
            order_mock.first.return_value = root_cause
            filter_mock.order_by.return_value = order_mock
            query_mock.filter.return_value = filter_mock
        elif model == Remediation:
            filter_mock = MagicMock()
            order_mock = MagicMock()
            order_mock.first.return_value = remediation
            filter_mock.order_by.return_value = order_mock
            query_mock.filter.return_value = filter_mock
        elif model == Approval:
            filter_mock = MagicMock()
            filter_mock.first.return_value = approval
            query_mock.filter.return_value = filter_mock
        elif model == Execution:
            filter_mock = MagicMock()
            filter_mock.first.return_value = execution
            query_mock.filter.return_value = filter_mock
        elif model == Verification:
            filter_mock = MagicMock()
            order_mock = MagicMock()
            order_mock.first.return_value = verification
            filter_mock.order_by.return_value = order_mock
            query_mock.filter.return_value = filter_mock
        elif model == Evaluation:
            filter_mock = MagicMock()
            order_mock = MagicMock()
            order_mock.first.return_value = existing_eval
            filter_mock.order_by.return_value = order_mock
            query_mock.filter.return_value = filter_mock
        else:
            filter_mock = MagicMock()
            filter_mock.all.return_value = []
            filter_mock.first.return_value = None
            query_mock.filter.return_value = filter_mock
        return query_mock

    db.query.side_effect = mock_query
    return db


# 1. Fully successful incident -> overall PASS
def test_fully_successful_incident_overall_pass():
    inc = Incident(
        id=1,
        incident_id="INC-SUCCESS-1",
        title="Payment Service DB Pool Spike",
        status=IncidentStatus.RESOLVED,
        severity=Severity.HIGH,
        affected_service="payment-service",
        fault_type="http_500_spike"
    )
    events = [
        IncidentEvent(id=1, incident_id=1, event_type="INVESTIGATION_STARTED", message="Started"),
        IncidentEvent(id=2, incident_id=1, event_type="AI_INVESTIGATION_COMPLETED", message="Completed"),
    ]
    evidence = [
        Evidence(id=1, incident_id=1, evidence_id="EVID-101", evidence_type="METRIC", source="prometheus", service="payment-service", summary="High error rate", payload={"rate": 0.5}),
        Evidence(id=2, incident_id=1, evidence_id="EVID-102", evidence_type="LOG", source="loki", service="payment-service", summary="DB timeout logs", payload={"log": "timeout"})
    ]
    rc = RootCause(
        id=1,
        incident_id=1,
        root_cause="Database connection pool exhaustion causing 500 spike",
        confidence=0.95,
        evidence_ids=["EVID-101", "EVID-102"],
        status="IDENTIFIED"
    )
    rem = Remediation(
        id=1,
        incident_id=1,
        action_type="RESTART_SERVICE",
        description="Restart payment-service container",
        status="APPROVED",
        parameters={"target_service": "payment-service", "instances": "one"}
    )
    approval = Approval(id=1, incident_id=1, remediation_id=1, status="APPROVED")
    execution = Execution(id=1, incident_id=1, remediation_id=1, status="SUCCESS", result="Service restarted")
    verification = Verification(
        id=1,
        incident_id=1,
        execution_id=1,
        status="VERIFIED_SUCCESS",
        summary="Service recovered successfully",
        metrics={"checks": [{"name": "service_health", "passed": True, "observed": "healthy", "expected": "healthy"}]}
    )

    db = create_mock_db(inc, events, evidence, None, rc, rem, approval, execution, verification)
    res = evaluate_incident(inc, db, persist=False)

    assert res.overall_status == "PASS"
    assert res.investigation_result == "PASS"
    assert res.rca_result == "PASS"
    assert res.remediation_result == "PASS"
    assert res.verification_result == "PASS"
    assert len(res.failures) == 0
    assert len(res.recommendations) > 0


# 2. Missing evidence -> investigation failure / partial result
def test_missing_evidence_investigation_failure():
    inc = Incident(
        id=2,
        incident_id="INC-NO-EVID",
        title="Unverified incident",
        status=IncidentStatus.INVESTIGATING,
        severity=Severity.MEDIUM,
        affected_service="order-service"
    )
    events = [IncidentEvent(id=1, incident_id=2, event_type="INVESTIGATION_STARTED", message="Started")]
    evidence = []  # No evidence collected

    db = create_mock_db(inc, events, evidence)
    res = evaluate_incident(inc, db, persist=False)

    assert res.investigation_result == "FAIL"
    assert res.overall_status == "FAIL"
    assert any("evidence.available" in f for f in res.failures)


# 3. RCA without evidence linkage -> RCA evaluation failure
def test_rca_without_evidence_linkage():
    inc = Incident(
        id=3,
        incident_id="INC-UNLINKED-RCA",
        title="Unlinked RCA incident",
        status=IncidentStatus.INVESTIGATING,
        severity=Severity.HIGH,
        affected_service="auth-service"
    )
    events = [IncidentEvent(id=1, incident_id=3, event_type="INVESTIGATION_STARTED", message="Started")]
    evidence = [Evidence(id=1, incident_id=3, evidence_id="EVID-REAL-1", summary="Log error", payload={"k": "v"})]
    rc = RootCause(
        id=1,
        incident_id=3,
        root_cause="Hallucinated error",
        confidence=0.9,
        evidence_ids=["EVID-FABRICATED-999"],  # Referenced ID not in collected evidence
        status="IDENTIFIED"
    )

    db = create_mock_db(inc, events, evidence, None, rc)
    res = evaluate_incident(inc, db, persist=False)

    assert res.rca_result == "FAIL"
    assert res.overall_status == "FAIL"
    assert any("rca.evidence_linked" in f for f in res.failures)


# 4. Missing remediation -> remediation NOT_EVALUABLE / PARTIAL
def test_missing_remediation_partial():
    inc = Incident(
        id=4,
        incident_id="INC-NO-REM",
        title="Investigated but no remediation",
        status=IncidentStatus.INVESTIGATING,
        severity=Severity.MEDIUM,
        affected_service="user-service"
    )
    events = [IncidentEvent(id=1, incident_id=4, event_type="INVESTIGATION_STARTED", message="Started")]
    evidence = [Evidence(id=1, incident_id=4, evidence_id="EVID-1", summary="Log error", payload={"err": 1})]
    rc = RootCause(id=1, incident_id=4, root_cause="Known bug", confidence=0.8, evidence_ids=["EVID-1"])

    db = create_mock_db(inc, events, evidence, None, rc, remediation=None)
    res = evaluate_incident(inc, db, persist=False)

    assert res.remediation_result == "PARTIAL"
    assert any("remediation.exists" in c.name for c in res.checks)


# 5. Remediation without risk assessment / unsupported action -> remediation failure
def test_remediation_unsupported_action_failure():
    inc = Incident(
        id=5,
        incident_id="INC-BAD-ACTION",
        title="Bad action remediation",
        status=IncidentStatus.MITIGATING,
        severity=Severity.HIGH,
        affected_service="payment-service"
    )
    rem = Remediation(
        id=1,
        incident_id=5,
        action_type="UNAUTHORIZED_SHELL_COMMAND",  # Not supported
        description="Run dangerous command",
        status="PENDING",
        parameters={"cmd": "rm -rf"}
    )
    events = [IncidentEvent(id=1, incident_id=5, event_type="INVESTIGATION_STARTED", message="Started")]
    evidence = [Evidence(id=1, incident_id=5, evidence_id="EVID-1", summary="Log error", payload={})]
    rc = RootCause(id=1, incident_id=5, root_cause="Issue", confidence=0.8, evidence_ids=["EVID-1"])

    db = create_mock_db(inc, events, evidence, None, rc, remediation=rem)
    res = evaluate_incident(inc, db, persist=False)

    assert res.remediation_result == "FAIL"
    assert any("remediation.action_valid" in f for f in res.failures)


# 6. Verification with all checks passing -> verification PASS
def test_verification_all_checks_passing():
    inc = Incident(id=6, incident_id="INC-VERIF-PASS", status=IncidentStatus.RESOLVED)
    exec_rec = Execution(id=1, incident_id=6, status="SUCCESS")
    verif = Verification(
        id=1,
        incident_id=6,
        execution_id=1,
        status="VERIFIED_SUCCESS",
        metrics={"checks": [
            {"name": "health_check", "passed": True, "observed": "healthy", "expected": "healthy"},
            {"name": "latency_check", "passed": True, "observed": "40ms", "expected": "<100ms"}
        ]}
    )

    verif_status, checks = evaluate_verification(inc, verif, exec_rec)
    assert verif_status == "PASS"
    assert all(c.passed for c in checks)


# 7. Verification with mixed results -> verification PARTIAL
def test_verification_mixed_results_partial():
    inc = Incident(id=7, incident_id="INC-VERIF-PARTIAL", status=IncidentStatus.INVESTIGATING)
    exec_rec = Execution(id=1, incident_id=7, status="SUCCESS")
    verif = Verification(
        id=1,
        incident_id=7,
        execution_id=1,
        status="VERIFIED_FAILURE",
        metrics={"checks": [
            {"name": "health_check", "passed": True, "observed": "healthy", "expected": "healthy"},
            {"name": "replica_count", "passed": False, "observed": "1", "expected": "3"}
        ]}
    )

    verif_status, checks = evaluate_verification(inc, verif, exec_rec)
    assert verif_status == "PARTIAL"


# 8. Verification with failed critical checks -> verification FAIL
def test_verification_failed_critical_checks():
    inc = Incident(id=8, incident_id="INC-VERIF-FAIL", status=IncidentStatus.INVESTIGATING)
    exec_rec = Execution(id=1, incident_id=8, status="SUCCESS")
    verif = Verification(
        id=1,
        incident_id=8,
        execution_id=1,
        status="VERIFIED_FAILURE",
        metrics={"checks": [
            {"name": "health_check", "passed": False, "observed": "unhealthy", "expected": "healthy"}
        ]}
    )

    verif_status, checks = evaluate_verification(inc, verif, exec_rec)
    assert verif_status == "FAIL"


# 9. Unknown incident -> HTTP 404
def test_unknown_incident_404():
    db = MagicMock()
    filter_mock = MagicMock()
    filter_mock.first.return_value = None
    db.query.return_value.filter.return_value = filter_mock

    with pytest.raises(HTTPException) as exc_info:
        get_incident_evaluation("INC-NONEXISTENT", db)
    assert exc_info.value.status_code == 404


# 10. Evaluation must not mutate infrastructure state
def test_evaluator_does_not_mutate_infrastructure():
    service_name = "test-eval-service"
    update_simulated_state(service_name, {"status": "unhealthy", "replicas": 1})
    state_before = dict(get_simulated_state(service_name))

    inc = Incident(
        id=10,
        incident_id="INC-SAFETY-10",
        title="Safety Check Incident",
        status=IncidentStatus.INVESTIGATING,
        severity=Severity.HIGH,
        affected_service=service_name
    )
    rem = Remediation(
        id=1,
        incident_id=10,
        action_type="RESTART_SERVICE",
        parameters={"target_service": service_name}
    )

    db = create_mock_db(inc, remediation=rem)
    res = evaluate_incident(inc, db, persist=False)

    state_after = get_simulated_state(service_name)
    assert state_before == state_after
    assert state_after["status"] == "unhealthy"


# 11. Service-level evaluation with persist=False is strictly read-only
def test_evaluate_incident_persist_false_is_read_only():
    from app.services.evaluation import evaluate_incident

    inc = Incident(id=11, incident_id="INC-GET-TEST", status=IncidentStatus.DETECTED)
    db = create_mock_db(inc)
    db.add = MagicMock()
    db.commit = MagicMock()
    db.delete = MagicMock()

    # Call the core evaluation function with persist=False (service-level read-only test)
    response = evaluate_incident(inc, db, persist=False)

    # Verify response contains the expected evaluation data structure
    assert getattr(response, "overall_status", None) is not None

    # Assert that no database mutations occurred
    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.delete.assert_not_called()
