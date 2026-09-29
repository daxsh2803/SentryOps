import sys
import os
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from fastapi import HTTPException

from app.models.all import (
    Incident,
    IncidentStatus,
    Severity,
    IncidentEvent,
    Evidence,
    AgentExecution,
    RootCause,
    Remediation,
    Approval,
    Execution,
    Verification,
    Evaluation,
)
from app.services.evaluation import evaluate_incident
from app.services.replay import build_replay, get_incident_replay_by_id
from app.services.postmortem import build_postmortem, get_incident_postmortem_by_id
from app.services.remediation import get_simulated_state, SIMULATED_INFRA_STATE

BASE_TIME = datetime(2026, 1, 1, 12, 0, 0)


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
    recorded_evaluation=None,
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
        elif model == AgentExecution:
            filter_mock = MagicMock()
            filter_mock.all.return_value = agent_executions
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
            order_mock.first.return_value = recorded_evaluation
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


def build_completed_incident():
    """Fully progressed, verified incident used across replay/postmortem tests."""
    inc = Incident(
        id=1,
        incident_id="INC-PHASE12-1",
        title="Payment DB pool exhaustion",
        description="Elevated 500s on payment-service",
        status=IncidentStatus.RESOLVED,
        severity=Severity.HIGH,
        affected_service="payment-service",
        fault_type="http_500_spike",
        created_at=BASE_TIME,
        started_at=BASE_TIME + timedelta(minutes=1),
        resolved_at=BASE_TIME + timedelta(minutes=20),
    )
    events = [
        IncidentEvent(id=1, incident_id=1, event_type="INCIDENT_CREATED", source="incident-api",
                      message="Incident created", timestamp=BASE_TIME),
        IncidentEvent(id=2, incident_id=1, event_type="INVESTIGATION_STARTED", source="incident-api",
                      message="Started", timestamp=BASE_TIME + timedelta(minutes=2)),
        IncidentEvent(id=3, incident_id=1, event_type="AI_INVESTIGATION_COMPLETED", source="ai-investigator",
                      message="Completed", timestamp=BASE_TIME + timedelta(minutes=5)),
        IncidentEvent(id=4, incident_id=1, event_type="APPROVAL_RESOLVED", source="incident-api",
                      message="Remediation approved", timestamp=BASE_TIME + timedelta(minutes=10)),
        IncidentEvent(id=5, incident_id=1, event_type="ACTION_EXECUTED", source="incident-api",
                      message="Action execution", timestamp=BASE_TIME + timedelta(minutes=11)),
        IncidentEvent(id=6, incident_id=1, event_type="INCIDENT_RESOLVED", source="incident-api",
                      message="Incident verified resolved", timestamp=BASE_TIME + timedelta(minutes=15)),
    ]
    evidence = [
        Evidence(id=1, incident_id=1, evidence_id="EVID-101", evidence_type="METRIC", source="prometheus",
                 service="payment-service", summary="Error rate spike", payload={"rate": 0.5}, confidence=0.9),
        Evidence(id=2, incident_id=1, evidence_id="EVID-102", evidence_type="LOG", source="loki",
                 service="payment-service", summary="DB timeout logs", payload={"log": "timeout"}, confidence=0.8),
    ]
    agents = [
        AgentExecution(id=i + 1, incident_id=1, agent_name=name, status="COMPLETED",
                       started_at=BASE_TIME + timedelta(minutes=2),
                       completed_at=BASE_TIME + timedelta(minutes=3))
        for i, name in enumerate(["IncidentManager", "LogAgent", "MetricsAgent", "RCAAgent"])
    ]
    root_cause = RootCause(
        id=1, incident_id=1,
        root_cause="Database connection pool exhaustion causing 500 spike",
        confidence=0.95, evidence_ids=["EVID-101", "EVID-102"], status="IDENTIFIED",
        identified_at=BASE_TIME + timedelta(minutes=5),
    )
    remediation = Remediation(
        id=1, incident_id=1, action_type="RESTART_SERVICE",
        description="Restart payment-service container", status="APPROVED",
        parameters={"target_service": "payment-service", "instances": "one"},
        created_at=BASE_TIME + timedelta(minutes=8),
    )
    approval = Approval(id=1, incident_id=1, remediation_id=1, status="APPROVED",
                        requested_at=BASE_TIME + timedelta(minutes=8),
                        resolved_at=BASE_TIME + timedelta(minutes=10))
    execution = Execution(id=1, incident_id=1, remediation_id=1, status="SUCCESS",
                          result="Successfully restarted service payment-service",
                          started_at=BASE_TIME + timedelta(minutes=11),
                          completed_at=BASE_TIME + timedelta(minutes=11))
    verification = Verification(
        id=1, incident_id=1, execution_id=1, status="VERIFIED_SUCCESS",
        summary="Service recovered successfully",
        metrics={"checks": [
            {"name": "service_exists", "passed": True, "observed": "payment-service", "expected": "payment-service"},
            {"name": "service_health", "passed": True, "observed": "healthy", "expected": "healthy"},
        ]},
        created_at=BASE_TIME + timedelta(minutes=15),
    )
    return inc, events, evidence, agents, root_cause, remediation, approval, execution, verification


def recorded_evaluation_from(inc, db):
    """Build a persisted Evaluation mirroring the recomputed evaluation."""
    pre = evaluate_incident(inc, db, persist=False)
    return pre, Evaluation(
        id=1, incident_id=inc.id, evaluation_id="EVAL-RECORDED",
        overall_status=pre.overall_status, summary=pre.summary,
        investigation_status=pre.investigation_result, rca_status=pre.rca_result,
        remediation_status=pre.remediation_result, verification_status=pre.verification_result,
        checks=[c.model_dump() for c in pre.checks], failures=pre.failures,
        recommendations=pre.recommendations, evaluated_at=BASE_TIME + timedelta(minutes=16),
    )


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------

def test_valid_incident_replay_consistent():
    inc, events, ev, agents, rc, rem, appr, exe, verif = build_completed_incident()
    db = create_mock_db(inc, events, ev, agents, rc, rem, appr, exe, verif)
    pre, recorded = recorded_evaluation_from(inc, db)
    db = create_mock_db(inc, events, ev, agents, rc, rem, appr, exe, verif, recorded_evaluation=recorded)

    result = build_replay(inc, db)

    assert result.replay_consistency == "MATCH"
    assert result.incident_id == inc.incident_id
    assert result.incident_status == "RESOLVED"
    assert len(result.differences) > 0
    assert all(d.consistent for d in result.differences)
    # Every lifecycle stage is reconstructed.
    stages = {s.stage for s in result.stages}
    assert {"INCIDENT", "EVIDENCE", "INVESTIGATION", "ROOT_CAUSE", "REMEDIATION",
            "RISK", "APPROVAL", "EXECUTION", "VERIFICATION", "EVALUATION"} <= stages


def test_replay_missing_incident_404():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(HTTPException) as exc:
        get_incident_replay_by_id("INC-DOES-NOT-EXIST", db)
    assert exc.value.status_code == 404


def test_replay_incomplete_incident_is_incomplete():
    inc = Incident(id=2, incident_id="INC-PHASE12-EMPTY", title="Detected only",
                   status=IncidentStatus.DETECTED, severity=Severity.LOW)
    db = create_mock_db(inc)
    result = build_replay(inc, db)

    assert result.replay_consistency == "INCOMPLETE"
    assert result.differences == []
    assert result.historical_actions == []
    # Core lifecycle stages are reported as unavailable rather than fabricated.
    by_stage = {s.stage: s for s in result.stages}
    assert by_stage["ROOT_CAUSE"].available is False
    assert by_stage["REMEDIATION"].available is False
    assert by_stage["VERIFICATION"].available is False


def test_replay_is_deterministic():
    inc, events, ev, agents, rc, rem, appr, exe, verif = build_completed_incident()
    db = create_mock_db(inc, events, ev, agents, rc, rem, appr, exe, verif)

    first = build_replay(inc, db)
    second = build_replay(inc, db)

    exclude = {"replay_id", "replayed_at"}
    assert first.model_dump(exclude=exclude) == second.model_dump(exclude=exclude)


def test_replay_comparison_detects_mismatch():
    """A stale recorded evaluation must surface as an explicit mismatch."""
    inc = Incident(id=3, incident_id="INC-PHASE12-DRIFT", title="Drifted",
                   status=IncidentStatus.INVESTIGATING, severity=Severity.MEDIUM,
                   affected_service="order-service")
    events = [IncidentEvent(id=1, incident_id=3, event_type="INVESTIGATION_STARTED",
                            message="Started", timestamp=BASE_TIME)]
    # No evidence -> replay evaluation fails investigation; recorded eval claims PASS.
    recorded = Evaluation(id=9, incident_id=3, evaluation_id="EVAL-STALE",
                          overall_status="PASS", investigation_status="PASS",
                          rca_status="PASS", remediation_status="PASS",
                          verification_status="PASS", evaluated_at=BASE_TIME)

    db = create_mock_db(inc, events, evidence=[], recorded_evaluation=recorded)
    result = build_replay(inc, db)

    assert result.replay_consistency == "MISMATCH"
    inconsistent = {d.field for d in result.differences if not d.consistent}
    assert "evaluation.overall_status" in inconsistent
    assert "evaluation.investigation_result" in inconsistent


def test_replay_reports_broken_verification_status():
    """Recorded verification status inconsistent with its checks is flagged."""
    inc, events, ev, agents, rc, rem, appr, exe, verif = build_completed_incident()
    verif.status = "VERIFIED_SUCCESS"
    verif.metrics = {"checks": [{"name": "service_health", "passed": False,
                                 "observed": "unhealthy", "expected": "healthy"}]}
    db = create_mock_db(inc, events, ev, agents, rc, rem, appr, exe, verif)

    result = build_replay(inc, db)
    diff = next(d for d in result.differences if d.field == "verification.status")
    assert diff.consistent is False
    assert diff.replay == "VERIFIED_FAILURE"
    assert result.replay_consistency == "MISMATCH"


# ---------------------------------------------------------------------------
# Phase 12 safety: replay must never execute remediation or mutate infrastructure
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("action_type", ["RESTART_SERVICE", "SCALE_SERVICE", "ROLLBACK_SERVICE"])
def test_replay_does_not_execute_historical_remediation(action_type):
    inc, events, ev, agents, rc, rem, appr, exe, verif = build_completed_incident()
    service = "phase12-safety-service"
    rem.action_type = action_type
    rem.parameters = {"target_service": service, "replicas": 3, "version": "previous"}

    # Establish a known simulated infrastructure state.
    get_simulated_state(service)
    SIMULATED_INFRA_STATE[service].update({"status": "unhealthy", "replicas": 1, "version": "current"})
    before = dict(SIMULATED_INFRA_STATE[service])

    db = create_mock_db(inc, events, ev, agents, rc, rem, appr, exe, verif)

    with patch("app.services.remediation.execute_controlled_action",
               side_effect=AssertionError("execute_controlled_action must not run during replay")) as exec_mock, \
         patch("app.services.remediation.restart_service",
               side_effect=AssertionError("restart_service must not run during replay")) as restart_mock, \
         patch("app.services.remediation.scale_service",
               side_effect=AssertionError("scale_service must not run during replay")) as scale_mock, \
         patch("app.services.remediation.rollback_service",
               side_effect=AssertionError("rollback_service must not run during replay")) as rollback_mock, \
         patch("app.services.remediation.update_simulated_state",
               side_effect=AssertionError("infrastructure state must not be mutated during replay")) as update_mock:
        result = build_replay(inc, db)

    exec_mock.assert_not_called()
    restart_mock.assert_not_called()
    scale_mock.assert_not_called()
    rollback_mock.assert_not_called()
    update_mock.assert_not_called()

    # The action is surfaced only as historical data.
    assert len(result.historical_actions) == 1
    action = result.historical_actions[0]
    assert action.action_type == action_type
    assert "Historical" in action.note

    after = dict(SIMULATED_INFRA_STATE[service])
    assert before == after
    assert after["status"] == "unhealthy"


def test_postmortem_does_not_execute_historical_remediation():
    inc, events, ev, agents, rc, rem, appr, exe, verif = build_completed_incident()
    db = create_mock_db(inc, events, ev, agents, rc, rem, appr, exe, verif)

    with patch("app.services.remediation.execute_controlled_action",
               side_effect=AssertionError("must not execute")) as exec_mock, \
         patch("app.services.remediation.update_simulated_state",
               side_effect=AssertionError("must not mutate infra")) as update_mock:
        build_postmortem(inc, db)

    exec_mock.assert_not_called()
    update_mock.assert_not_called()


def test_replay_is_read_only():
    inc, events, ev, agents, rc, rem, appr, exe, verif = build_completed_incident()
    db = create_mock_db(inc, events, ev, agents, rc, rem, appr, exe, verif)
    db.add = MagicMock()
    db.commit = MagicMock()
    db.delete = MagicMock()
    db.flush = MagicMock()

    build_replay(inc, db)

    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.delete.assert_not_called()
    db.flush.assert_not_called()


# ---------------------------------------------------------------------------
# Postmortem
# ---------------------------------------------------------------------------

def test_postmortem_valid_completed_incident():
    inc, events, ev, agents, rc, rem, appr, exe, verif = build_completed_incident()
    db = create_mock_db(inc, events, ev, agents, rc, rem, appr, exe, verif)

    pm = build_postmortem(inc, db)

    assert pm.incident_id == inc.incident_id
    assert pm.final_status == "RESOLVED"
    assert pm.summary
    assert pm.impact
    sections = {s.section: s for s in pm.sections}
    assert set(sections) == {"DETECTION", "INVESTIGATION", "EVIDENCE", "ROOT_CAUSE",
                             "REMEDIATION", "APPROVAL", "EXECUTION", "VERIFICATION", "EVALUATION"}
    for name in ["DETECTION", "INVESTIGATION", "EVIDENCE", "ROOT_CAUSE",
                 "REMEDIATION", "APPROVAL", "EXECUTION", "VERIFICATION", "EVALUATION"]:
        assert sections[name].available is True, name
    assert len(pm.lessons) > 0


def test_postmortem_timeline_construction():
    inc, events, ev, agents, rc, rem, appr, exe, verif = build_completed_incident()
    db = create_mock_db(inc, events, ev, agents, rc, rem, appr, exe, verif)

    pm = build_postmortem(inc, db)

    assert len(pm.timeline) >= len(events)
    stamped = [e for e in pm.timeline if e.timestamp is not None]
    # Timeline is chronologically ordered.
    assert stamped == sorted(stamped, key=lambda e: e.timestamp)
    events_in_timeline = {e.event for e in pm.timeline}
    assert "AI_INVESTIGATION_COMPLETED" in events_in_timeline
    assert "INCIDENT_RESOLVED" in events_in_timeline
    assert "ROOT_CAUSE_IDENTIFIED" in events_in_timeline
    assert "VERIFICATION_PERFORMED" in events_in_timeline


def test_postmortem_does_not_fabricate_missing_timestamps():
    inc, events, ev, agents, rc, rem, appr, exe, verif = build_completed_incident()
    rem.created_at = None
    db = create_mock_db(inc, events, ev, agents, rc, rem, appr, exe, verif)

    pm = build_postmortem(inc, db)
    entry = next(e for e in pm.timeline if e.event == "REMEDIATION_PROPOSED")
    assert entry.timestamp is None
    # Missing-timestamp entries sort last rather than being assigned an invented time.
    assert pm.timeline[-1].timestamp is None


def test_postmortem_includes_rca_remediation_verification_evaluation():
    inc, events, ev, agents, rc, rem, appr, exe, verif = build_completed_incident()
    db = create_mock_db(inc, events, ev, agents, rc, rem, appr, exe, verif)

    pm = build_postmortem(inc, db)
    sections = {s.section: s for s in pm.sections}

    assert sections["ROOT_CAUSE"].details["root_cause"] == rc.root_cause
    assert sections["REMEDIATION"].details["action_type"] == "RESTART_SERVICE"
    assert sections["REMEDIATION"].details["risk"]["risk_level"] in {"LOW", "MEDIUM", "HIGH"}
    assert sections["VERIFICATION"].details["status"] == "VERIFIED_SUCCESS"
    assert sections["EVALUATION"].details["recomputed"]["overall_status"] in {"PASS", "PARTIAL", "FAIL", "NOT_EVALUABLE"}
    assert sections["EXECUTION"].details["note"].startswith("Historical record only")


def test_postmortem_incomplete_incident_handled_safely():
    inc = Incident(id=5, incident_id="INC-PHASE12-NEW", title="Just detected",
                   status=IncidentStatus.DETECTED, severity=Severity.LOW,
                   affected_service="user-service")
    db = create_mock_db(inc)

    pm = build_postmortem(inc, db)

    assert len(pm.sections) == 9
    by_section = {s.section: s for s in pm.sections}
    assert by_section["ROOT_CAUSE"].available is False
    assert by_section["REMEDIATION"].available is False
    assert by_section["EXECUTION"].available is False
    assert by_section["VERIFICATION"].available is False
    # Evaluation is always available because it is deterministically recomputed.
    assert by_section["EVALUATION"].available is True
    assert pm.timeline == []


def test_postmortem_missing_incident_404():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(HTTPException) as exc:
        get_incident_postmortem_by_id("INC-MISSING", db)
    assert exc.value.status_code == 404


def test_postmortem_is_read_only():
    inc, events, ev, agents, rc, rem, appr, exe, verif = build_completed_incident()
    db = create_mock_db(inc, events, ev, agents, rc, rem, appr, exe, verif)
    db.add = MagicMock()
    db.commit = MagicMock()
    db.delete = MagicMock()
    db.flush = MagicMock()

    build_postmortem(inc, db)

    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.delete.assert_not_called()
    db.flush.assert_not_called()


def test_replay_and_postmortem_are_json_serializable():
    inc, events, ev, agents, rc, rem, appr, exe, verif = build_completed_incident()
    db = create_mock_db(inc, events, ev, agents, rc, rem, appr, exe, verif)

    assert isinstance(build_replay(inc, db).model_dump(), dict)
    assert isinstance(build_postmortem(inc, db).model_dump(), dict)
