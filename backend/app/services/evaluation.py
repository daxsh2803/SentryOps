from typing import Dict, Any, List, Optional
import uuid
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.all import (
    Incident,
    IncidentStatus,
    IncidentEvent,
    Evidence,
    AgentExecution,
    RootCause,
    Remediation,
    Approval,
    Execution,
    Verification,
    Evaluation
)
from app.schemas.all import EvaluationCheck, EvaluationResult

logger = logging.getLogger(__name__)

SUPPORTED_ACTIONS = {
    "RESTART_SERVICE",
    "SCALE_SERVICE",
    "ROLLBACK_SERVICE"
}

def evaluate_investigation(
    incident: Incident,
    events: List[IncidentEvent],
    evidence_items: List[Evidence],
    agent_executions: List[AgentExecution]
) -> tuple[str, List[EvaluationCheck]]:
    checks: List[EvaluationCheck] = []

    # 1. Investigation started / completed check
    has_inv_events = any(
        e.event_type in {"INVESTIGATION_STARTED", "AI_INVESTIGATION_STARTED", "AI_INVESTIGATION_COMPLETED"}
        for e in events
    )
    has_agent_execs = len(agent_executions) > 0
    is_not_detected = incident.status != IncidentStatus.DETECTED

    investigation_ran = has_inv_events or has_agent_execs or is_not_detected
    if not investigation_ran and len(evidence_items) == 0:
        checks.append(EvaluationCheck(
            name="investigation.started",
            dimension="INVESTIGATION",
            passed=False,
            observed=f"Incident status is {incident.status.value}; no investigation events",
            expected="Investigation started or completed",
            details="Incident remains in initial DETECTED state."
        ))
        return "NOT_EVALUABLE", checks

    checks.append(EvaluationCheck(
        name="investigation.started",
        dimension="INVESTIGATION",
        passed=True,
        observed=f"Investigation initiated (status: {incident.status.value}, events: {len(events)})",
        expected="Investigation started or completed"
    ))

    # 2. Evidence collected check
    ev_count = len(evidence_items)
    evidence_collected = ev_count > 0
    checks.append(EvaluationCheck(
        name="evidence.available",
        dimension="INVESTIGATION",
        passed=evidence_collected,
        observed=f"{ev_count} evidence items recorded",
        expected="At least 1 evidence item collected for the incident",
        details=None if evidence_collected else "Investigation failed to collect supporting telemetry evidence."
    ))

    # 3. Evidence quality check (non-empty summary / payload)
    if evidence_collected:
        valid_items = [e for e in evidence_items if e.evidence_id and (e.summary or e.payload)]
        all_valid = len(valid_items) == ev_count
        checks.append(EvaluationCheck(
            name="evidence.quality",
            dimension="INVESTIGATION",
            passed=all_valid,
            observed=f"{len(valid_items)} of {ev_count} evidence items have complete payload/summary",
            expected="All evidence items contain valid payload and summary",
            details=None if all_valid else "Some evidence records contain empty payload and summary."
        ))
    else:
        all_valid = False

    # 4. Agent executions check
    if has_agent_execs:
        failed_agents = [ae.agent_name for ae in agent_executions if ae.status == "FAILED" or ae.error]
        agents_ok = len(failed_agents) == 0
        checks.append(EvaluationCheck(
            name="investigation.agents_successful",
            dimension="INVESTIGATION",
            passed=agents_ok,
            observed=f"{len(agent_executions)} agents executed" if agents_ok else f"Failed agents: {', '.join(failed_agents)}",
            expected="All agent executions succeed without errors",
            details=None if agents_ok else f"Investigation agents encountered errors: {failed_agents}"
        ))
    else:
        agents_ok = True

    # Aggregate Investigation Result
    if not evidence_collected:
        status = "FAIL"
    elif all_valid and agents_ok:
        status = "PASS"
    else:
        status = "PARTIAL"

    return status, checks


def evaluate_rca(
    incident: Incident,
    root_cause: Optional[RootCause],
    evidence_items: List[Evidence],
    investigation_status: str
) -> tuple[str, List[EvaluationCheck]]:
    checks: List[EvaluationCheck] = []

    # 1. RCA exists
    if not root_cause:
        if investigation_status == "NOT_EVALUABLE":
            checks.append(EvaluationCheck(
                name="rca.exists",
                dimension="RCA",
                passed=False,
                observed="No RCA recorded (investigation not yet evaluated)",
                expected="Root cause analysis generated",
                details="Investigation has not completed to produce an RCA."
            ))
            return "NOT_EVALUABLE", checks
        else:
            checks.append(EvaluationCheck(
                name="rca.exists",
                dimension="RCA",
                passed=False,
                observed="No RCA recorded for completed investigation",
                expected="Root cause analysis generated",
                details="Investigation was executed but no root cause analysis was saved."
            ))
            return "FAIL", checks

    checks.append(EvaluationCheck(
        name="rca.exists",
        dimension="RCA",
        passed=True,
        observed=f"RCA identified: {root_cause.root_cause[:60]}...",
        expected="Root cause analysis generated"
    ))

    # 2. Non-empty root cause
    has_rc_text = bool(root_cause.root_cause and root_cause.root_cause.strip())
    checks.append(EvaluationCheck(
        name="rca.content_valid",
        dimension="RCA",
        passed=has_rc_text,
        observed="Valid root cause description" if has_rc_text else "Empty root cause description",
        expected="Non-empty root cause explanation",
        details=None if has_rc_text else "RCA record exists but contains an empty root cause string."
    ))

    # 3. Confidence score validity
    conf = root_cause.confidence
    valid_conf = conf is not None and (0.0 <= conf <= 1.0)
    checks.append(EvaluationCheck(
        name="rca.confidence_valid",
        dimension="RCA",
        passed=valid_conf,
        observed=f"Confidence: {conf}",
        expected="Confidence score between 0.0 and 1.0",
        details=None if valid_conf else "RCA confidence score is missing or outside valid range [0.0, 1.0]."
    ))

    # 4. Evidence linkage
    rc_ev_ids = root_cause.evidence_ids or []
    existing_ev_ids = set(e.evidence_id for e in evidence_items)
    if not rc_ev_ids:
        linkage_ok = False
        checks.append(EvaluationCheck(
            name="rca.evidence_linked",
            dimension="RCA",
            passed=False,
            observed="RCA contains 0 linked evidence IDs",
            expected="RCA links to at least 1 collected evidence item",
            details="RCA was synthesized without referencing any collected evidence IDs."
        ))
    else:
        invalid_ids = [eid for eid in rc_ev_ids if eid not in existing_ev_ids]
        if invalid_ids:
            linkage_ok = False
            checks.append(EvaluationCheck(
                name="rca.evidence_linked",
                dimension="RCA",
                passed=False,
                observed=f"RCA references uncollected evidence IDs: {invalid_ids}",
                expected="All referenced evidence IDs exist in collected incident evidence",
                details=f"Uncollected or hallucinated evidence IDs referenced: {invalid_ids}"
            ))
        else:
            linkage_ok = True
            checks.append(EvaluationCheck(
                name="rca.evidence_linked",
                dimension="RCA",
                passed=True,
                observed=f"RCA successfully linked to {len(rc_ev_ids)} valid evidence items",
                expected="All referenced evidence IDs exist in collected incident evidence"
            ))

    # Aggregate RCA Result
    if not has_rc_text or not valid_conf or not linkage_ok:
        status = "FAIL"
    else:
        status = "PASS"

    return status, checks


def evaluate_remediation(
    incident: Incident,
    remediation: Optional[Remediation],
    approval: Optional[Approval],
    execution: Optional[Execution],
    investigation_status: str,
    rca_status: str
) -> tuple[str, List[EvaluationCheck]]:
    checks: List[EvaluationCheck] = []

    # 1. Remediation exists
    if not remediation:
        if investigation_status == "NOT_EVALUABLE" or rca_status == "NOT_EVALUABLE":
            checks.append(EvaluationCheck(
                name="remediation.exists",
                dimension="REMEDIATION",
                passed=False,
                observed="No remediation proposal recorded (prior stages incomplete)",
                expected="Remediation proposal generated",
                details="Lifecycle has not progressed to remediation."
            ))
            return "NOT_EVALUABLE", checks
        else:
            checks.append(EvaluationCheck(
                name="remediation.exists",
                dimension="REMEDIATION",
                passed=False,
                observed="No remediation proposal recorded",
                expected="Remediation proposal generated",
                details="Incident was investigated with an RCA, but no remediation was proposed."
            ))
            return "PARTIAL", checks

    checks.append(EvaluationCheck(
        name="remediation.exists",
        dimension="REMEDIATION",
        passed=True,
        observed=f"Remediation proposal present: {remediation.action_type}",
        expected="Remediation proposal generated"
    ))

    # 2. Action type validity
    is_action_valid = remediation.action_type in SUPPORTED_ACTIONS
    checks.append(EvaluationCheck(
        name="remediation.action_valid",
        dimension="REMEDIATION",
        passed=is_action_valid,
        observed=f"Action type: {remediation.action_type}",
        expected=f"Supported action in {sorted(list(SUPPORTED_ACTIONS))}",
        details=None if is_action_valid else f"Action '{remediation.action_type}' is not in the controlled allowlist."
    ))

    # 3. Target service validity
    params = remediation.parameters or {}
    target_service = params.get("target_service") or incident.affected_service
    has_target = bool(target_service and target_service.strip())
    checks.append(EvaluationCheck(
        name="remediation.target_service",
        dimension="REMEDIATION",
        passed=has_target,
        observed=f"Target service: {target_service}" if has_target else "Target service missing",
        expected="Target service specified in parameters or incident",
        details=None if has_target else "Remediation parameters lack a target_service."
    ))

    # 4. Risk Assessment check
    from app.services.remediation import evaluate_risk
    from app.schemas.all import RemediationProposal
    try:
        prop = RemediationProposal(
            action_type=remediation.action_type,
            target_service=target_service or "unknown",
            parameters=params,
            reason=remediation.description or "",
            evidence_ids=[],
            confidence=1.0
        )
        risk = evaluate_risk(prop)
        risk_evaluated = bool(risk and risk.risk_level in {"LOW", "MEDIUM", "HIGH"})
        checks.append(EvaluationCheck(
            name="remediation.risk_assessed",
            dimension="REMEDIATION",
            passed=risk_evaluated,
            observed=f"Risk level: {risk.risk_level} (Requires approval: {risk.requires_approval})",
            expected="Deterministic risk assessment produced with valid risk level"
        ))
    except Exception as ex:
        risk = None
        risk_evaluated = False
        checks.append(EvaluationCheck(
            name="remediation.risk_assessed",
            dimension="REMEDIATION",
            passed=False,
            observed=f"Risk assessment error: {ex}",
            expected="Deterministic risk assessment produced",
            details=str(ex)
        ))

    # 5. Approval policy respected
    approval_ok = True
    if approval:
        if approval.status == "APPROVED":
            checks.append(EvaluationCheck(
                name="remediation.approval_respected",
                dimension="REMEDIATION",
                passed=True,
                observed="Human approval granted",
                expected="Required approval obtained before execution"
            ))
        elif approval.status == "REJECTED":
            if execution and execution.status == "SUCCESS":
                approval_ok = False
                checks.append(EvaluationCheck(
                    name="remediation.approval_respected",
                    dimension="REMEDIATION",
                    passed=False,
                    observed="Action was executed despite approval being REJECTED",
                    expected="Action must not execute when rejected",
                    details="Safety violation: controlled execution occurred on rejected proposal."
                ))
            else:
                checks.append(EvaluationCheck(
                    name="remediation.approval_respected",
                    dimension="REMEDIATION",
                    passed=True,
                    observed="Remediation rejected by operator; execution safely halted",
                    expected="Action halted upon rejection"
                ))
        elif approval.status == "PENDING":
            if execution:
                approval_ok = False
                checks.append(EvaluationCheck(
                    name="remediation.approval_respected",
                    dimension="REMEDIATION",
                    passed=False,
                    observed="Execution initiated while approval is still PENDING",
                    expected="Action must not execute prior to approval",
                    details="Safety violation: premature execution before approval resolution."
                ))
            else:
                checks.append(EvaluationCheck(
                    name="remediation.approval_respected",
                    dimension="REMEDIATION",
                    passed=True,
                    observed="Remediation pending operator approval",
                    expected="Awaiting approval before execution"
                ))
    else:
        # No approval record in DB
        if risk and risk.requires_approval:
            if execution:
                approval_ok = False
                checks.append(EvaluationCheck(
                    name="remediation.approval_respected",
                    dimension="REMEDIATION",
                    passed=False,
                    observed="Action requiring approval executed without approval record",
                    expected="Approval required prior to execution",
                    details="High/Medium risk action executed without approval flow."
                ))
            else:
                approval_ok = False
                checks.append(EvaluationCheck(
                    name="remediation.approval_respected",
                    dimension="REMEDIATION",
                    passed=False,
                    observed="Action requires approval but no approval record was created",
                    expected="Approval workflow initiated for high/medium risk action",
                    details="Missing approval record for action requiring approval."
                ))
        else:
            checks.append(EvaluationCheck(
                name="remediation.approval_respected",
                dimension="REMEDIATION",
                passed=True,
                observed="Low risk action - eligible for auto-execution without approval record",
                expected="Approval policy satisfied"
            ))

    # 6. Execution result check
    execution_ok = True
    if execution:
        if execution.status == "SUCCESS":
            checks.append(EvaluationCheck(
                name="remediation.execution_result",
                dimension="REMEDIATION",
                passed=True,
                observed=f"Execution SUCCESS: {execution.result or 'Action completed'}",
                expected="Execution status SUCCESS"
            ))
        else:
            execution_ok = False
            checks.append(EvaluationCheck(
                name="remediation.execution_result",
                dimension="REMEDIATION",
                passed=False,
                observed=f"Execution status: {execution.status} (Error: {execution.error or execution.result})",
                expected="Execution status SUCCESS",
                details=f"Controlled execution failed: {execution.error or execution.result}"
            ))
    else:
        if approval and approval.status in {"PENDING", "REJECTED"}:
            checks.append(EvaluationCheck(
                name="remediation.execution_result",
                dimension="REMEDIATION",
                passed=True,
                observed=f"Execution appropriately omitted (approval status: {approval.status})",
                expected="Execution halted or pending approval"
            ))
        else:
            execution_ok = False
            checks.append(EvaluationCheck(
                name="remediation.execution_result",
                dimension="REMEDIATION",
                passed=False,
                observed="No execution record found for remediation proposal",
                expected="Execution record present",
                details="Remediation was proposed but execution was not completed or recorded."
            ))

    # Aggregate Remediation Result
    if not is_action_valid or not has_target or not risk_evaluated or not approval_ok:
        status = "FAIL"
    elif execution and execution.status == "FAILED":
        status = "FAIL"
    elif execution and execution.status == "SUCCESS":
        status = "PASS"
    elif approval and approval.status in {"PENDING", "REJECTED"}:
        status = "PARTIAL"
    else:
        status = "PARTIAL"

    return status, checks


def evaluate_verification(
    incident: Incident,
    verification: Optional[Verification],
    execution: Optional[Execution]
) -> tuple[str, List[EvaluationCheck]]:
    checks: List[EvaluationCheck] = []

    # 1. Verification exists
    if not verification:
        if execution and execution.status == "SUCCESS":
            checks.append(EvaluationCheck(
                name="verification.exists",
                dimension="VERIFICATION",
                passed=False,
                observed="Execution succeeded, but no post-remediation verification record found",
                expected="Verification record exists following execution",
                details="Verification was skipped or omitted after remediation execution."
            ))
            return "FAIL", checks
        else:
            checks.append(EvaluationCheck(
                name="verification.exists",
                dimension="VERIFICATION",
                passed=False,
                observed="Verification not yet performed (execution incomplete or pending)",
                expected="Verification executed after remediation",
                details="Incident lifecycle has not reached verification stage."
            ))
            return "NOT_EVALUABLE", checks

    checks.append(EvaluationCheck(
        name="verification.exists",
        dimension="VERIFICATION",
        passed=True,
        observed=f"Verification record present (Status: {verification.status})",
        expected="Verification record exists"
    ))

    # 2. Verification checks present
    metrics = verification.metrics or {}
    v_checks = metrics.get("checks", [])
    has_checks = len(v_checks) > 0
    checks.append(EvaluationCheck(
        name="verification.checks_present",
        dimension="VERIFICATION",
        passed=has_checks,
        observed=f"{len(v_checks)} verification checks recorded",
        expected="At least 1 individual verification check present",
        details=None if has_checks else "Verification record contains empty checks list."
    ))

    # 3. Individual checks outcome
    if has_checks:
        passed_count = sum(1 for c in v_checks if c.get("passed", False))
        all_passed = (passed_count == len(v_checks))
        any_passed = (passed_count > 0)

        checks.append(EvaluationCheck(
            name="verification.checks_outcome",
            dimension="VERIFICATION",
            passed=all_passed,
            observed=f"{passed_count} of {len(v_checks)} checks passed",
            expected="All verification checks pass",
            details=None if all_passed else f"Failing checks: {[c.get('name') for c in v_checks if not c.get('passed')]}"
        ))
    else:
        all_passed = False
        any_passed = False

    # 4. Status consistency check
    is_verified_status = (verification.status == "VERIFIED_SUCCESS")
    status_consistent = (is_verified_status == all_passed)
    checks.append(EvaluationCheck(
        name="verification.status_consistent",
        dimension="VERIFICATION",
        passed=status_consistent,
        observed=f"Verification status '{verification.status}' with {all_passed=}",
        expected="Verification status reflects check outcomes",
        details=None if status_consistent else "Mismatch between verification checks outcome and overall verification status."
    ))

    # 5. Incident status alignment
    if is_verified_status:
        aligned = (incident.status == IncidentStatus.RESOLVED or incident.status.value == "RESOLVED")
        checks.append(EvaluationCheck(
            name="verification.incident_status_aligned",
            dimension="VERIFICATION",
            passed=aligned,
            observed=f"Incident status is {incident.status.value}",
            expected="Incident status RESOLVED after verified recovery",
            details=None if aligned else "Incident was not marked RESOLVED despite successful verification."
        ))
    else:
        aligned = (incident.status == IncidentStatus.INVESTIGATING or incident.status.value == "INVESTIGATING")
        checks.append(EvaluationCheck(
            name="verification.incident_status_aligned",
            dimension="VERIFICATION",
            passed=aligned,
            observed=f"Incident status is {incident.status.value}",
            expected="Incident status INVESTIGATING (re-investigation required) following failed verification",
            details=None if aligned else "Incident was not moved to INVESTIGATING after failed verification."
        ))

    # Aggregate Verification Result
    if not has_checks or (not any_passed and len(v_checks) > 0):
        status = "FAIL"
    elif all_passed and is_verified_status and status_consistent:
        status = "PASS"
    elif any_passed and not all_passed:
        status = "PARTIAL"
    else:
        status = "FAIL"

    return status, checks


def build_recommendations(
    failures: List[str],
    inv_status: str,
    rca_status: str,
    rem_status: str,
    verif_status: str,
    overall_status: str
) -> List[str]:
    recs: List[str] = []

    if inv_status == "FAIL":
        recs.append("Ensure observability collectors (Prometheus, Loki, Jaeger) are properly instrumented and recording telemetry.")
    if rca_status == "FAIL":
        recs.append("Ensure RCA synthesizer directly links root-cause conclusions to valid collected evidence IDs.")
    if rem_status == "FAIL":
        recs.append("Inspect remediation execution logs and service environment parameters for configuration or permission errors.")
    elif rem_status == "PARTIAL":
        recs.append("Review pending remediation proposal and approval status to advance the remediation stage.")
    if verif_status == "FAIL":
        recs.append("Target service failed post-action health checks; re-investigation and corrective action are required.")
    elif verif_status == "PARTIAL":
        recs.append("Partial verification checks passed; investigate remaining unhealthy metrics before closing the incident.")

    if overall_status == "PASS":
        recs.append("Incident response lifecycle completed successfully with verified recovery. Retain telemetry for post-mortem analysis.")
    elif overall_status == "NOT_EVALUABLE":
        recs.append("Trigger AI investigation or manual evidence collection to begin the incident response lifecycle.")

    return recs


def evaluate_incident(
    incident: Incident,
    db: Session,
    persist: bool = True
) -> EvaluationResult:
    # 1. Fetch related data
    events = db.query(IncidentEvent).filter(IncidentEvent.incident_id == incident.id).order_by(IncidentEvent.timestamp.asc()).all()
    evidence_items = db.query(Evidence).filter(Evidence.incident_id == incident.id).all()
    agent_executions = db.query(AgentExecution).filter(AgentExecution.incident_id == incident.id).all()
    root_cause = db.query(RootCause).filter(RootCause.incident_id == incident.id).order_by(RootCause.id.desc()).first()
    remediation = db.query(Remediation).filter(Remediation.incident_id == incident.id).order_by(Remediation.id.desc()).first()

    approval = db.query(Approval).filter(Approval.remediation_id == remediation.id).first() if remediation else None
    execution = db.query(Execution).filter(Execution.remediation_id == remediation.id).first() if remediation else None
    verification = db.query(Verification).filter(Verification.incident_id == incident.id).order_by(Verification.id.desc()).first()

    # 2. Run deterministic evaluations across all 4 dimensions
    inv_status, inv_checks = evaluate_investigation(incident, events, evidence_items, agent_executions)
    rca_status, rca_checks = evaluate_rca(incident, root_cause, evidence_items, inv_status)
    rem_status, rem_checks = evaluate_remediation(incident, remediation, approval, execution, inv_status, rca_status)
    verif_status, verif_checks = evaluate_verification(incident, verification, execution)

    all_checks = inv_checks + rca_checks + rem_checks + verif_checks

    # 3. Determine Overall Status
    dim_statuses = [inv_status, rca_status, rem_status, verif_status]

    if all(s == "NOT_EVALUABLE" for s in dim_statuses):
        overall_status = "NOT_EVALUABLE"
        summary = "Incident response lifecycle has not progressed sufficiently for evaluation."
    elif any(s == "FAIL" for s in dim_statuses):
        overall_status = "FAIL"
        summary = "Incident response lifecycle failed one or more critical evaluation criteria."
    elif all(s == "PASS" for s in dim_statuses):
        overall_status = "PASS"
        summary = "Incident response lifecycle completed successfully with all stages verified."
    else:
        overall_status = "PARTIAL"
        summary = "Incident response lifecycle is partially complete or has non-critical warnings."

    # 4. Extract failures
    failures = [f"{c.name}: {c.observed} (Expected: {c.expected})" for c in all_checks if not c.passed]

    # 5. Extract recommendations
    recommendations = build_recommendations(failures, inv_status, rca_status, rem_status, verif_status, overall_status)

    eval_id = f"EVAL-{uuid.uuid4().hex[:6].upper()}"
    eval_time = datetime.utcnow()

    # 6. Optional persistence to Database
    if persist:
        # Check if an existing evaluation record exists for this incident
        existing_eval = db.query(Evaluation).filter(Evaluation.incident_id == incident.id).order_by(Evaluation.id.desc()).first()
        if existing_eval:
            existing_eval.overall_status = overall_status
            existing_eval.summary = summary
            existing_eval.investigation_status = inv_status
            existing_eval.rca_status = rca_status
            existing_eval.remediation_status = rem_status
            existing_eval.verification_status = verif_status
            existing_eval.checks = [c.model_dump() for c in all_checks]
            existing_eval.failures = failures
            existing_eval.recommendations = recommendations
            existing_eval.evaluated_at = eval_time
            eval_id = existing_eval.evaluation_id
            db.add(existing_eval)
        else:
            db_eval = Evaluation(
                evaluation_id=eval_id,
                incident_id=incident.id,
                overall_status=overall_status,
                summary=summary,
                investigation_status=inv_status,
                rca_status=rca_status,
                remediation_status=rem_status,
                verification_status=verif_status,
                checks=[c.model_dump() for c in all_checks],
                failures=failures,
                recommendations=recommendations,
                evaluated_at=eval_time
            )
            db.add(db_eval)
        db.commit()

    return EvaluationResult(
        evaluation_id=eval_id,
        incident_id=incident.incident_id,
        overall_status=overall_status,
        summary=summary,
        investigation_result=inv_status,
        rca_result=rca_status,
        remediation_result=rem_status,
        verification_result=verif_status,
        checks=all_checks,
        failures=failures,
        recommendations=recommendations,
        evaluated_at=eval_time
    )

def get_incident_evaluation_by_id(
    incident_id: str,
    db: Session,
    persist: bool = True
) -> EvaluationResult:
    from fastapi import HTTPException
    incident = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return evaluate_incident(incident, db, persist=persist)
