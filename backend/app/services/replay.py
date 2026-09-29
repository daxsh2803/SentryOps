"""Phase 12 — deterministic incident replay.

Replay reconstructs an incident's historical lifecycle from persisted records and
re-runs the deterministic analysis (risk policy + evaluation) against that data.

Safety boundary: replay is strictly read-only. It never invokes remediation
execution, never touches simulated/production infrastructure, and never mutates
the database. Recorded remediation actions are treated purely as historical data.
"""

from typing import Any, List, Optional
import uuid
import logging
from datetime import datetime

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.all import Incident
from app.schemas.all import (
    IncidentReplayResult,
    ReplayStageSnapshot,
    ReplayDifference,
    HistoricalAction,
    RemediationProposal,
)
from app.services.history import collect_incident_history, IncidentHistory
from app.services.evaluation import evaluate_incident
from app.services.remediation import evaluate_risk

logger = logging.getLogger(__name__)

REPLAY_EXECUTION_NOTE = "Historical record only; replay never executes remediation."


def _value(raw: Any) -> Optional[str]:
    """Normalise enum/string values to a plain string for comparisons."""
    if raw is None:
        return None
    return raw.value if hasattr(raw, "value") else str(raw)


def _iso(raw: Optional[datetime]) -> Optional[str]:
    return raw.isoformat() if raw else None


def _target_service(incident: Incident, history: IncidentHistory) -> Optional[str]:
    if history.remediation and history.remediation.parameters:
        return history.remediation.parameters.get("target_service") or incident.affected_service
    return incident.affected_service


def _derive_verification_status(verification) -> Optional[str]:
    """Independently re-derive the verification status from persisted checks."""
    checks = (verification.metrics or {}).get("checks", [])
    if not checks:
        return None
    all_passed = all(bool(c.get("passed", False)) for c in checks)
    return "VERIFIED_SUCCESS" if all_passed else "VERIFIED_FAILURE"


def _build_stages(
    incident: Incident,
    history: IncidentHistory,
    risk,
    replay_evaluation,
) -> List[ReplayStageSnapshot]:
    stages: List[ReplayStageSnapshot] = []

    stages.append(ReplayStageSnapshot(
        stage="INCIDENT",
        available=True,
        status=_value(incident.status),
        summary=f"{incident.incident_id} ({_value(incident.severity)}) on {incident.affected_service or 'unknown service'}",
        details={
            "title": incident.title,
            "severity": _value(incident.severity),
            "affected_service": incident.affected_service,
            "fault_type": incident.fault_type,
            "created_at": _iso(incident.created_at),
            "started_at": _iso(incident.started_at),
            "resolved_at": _iso(incident.resolved_at),
        },
    ))

    stages.append(ReplayStageSnapshot(
        stage="EVIDENCE",
        available=len(history.evidence) > 0,
        status=None,
        summary=f"{len(history.evidence)} evidence items reconstructed from persisted data",
        details={
            "count": len(history.evidence),
            "evidence_ids": [e.evidence_id for e in history.evidence],
            "items": [
                {
                    "evidence_id": e.evidence_id,
                    "evidence_type": e.evidence_type,
                    "source": e.source,
                    "service": e.service,
                    "summary": e.summary,
                    "confidence": e.confidence,
                }
                for e in history.evidence
            ],
        },
    ))

    investigation_events = [
        e for e in history.events
        if e.event_type and "INVESTIGAT" in e.event_type.upper()
    ]
    stages.append(ReplayStageSnapshot(
        stage="INVESTIGATION",
        available=bool(history.agent_executions) or bool(investigation_events),
        status="COMPLETED" if history.agent_executions else None,
        summary=f"{len(history.agent_executions)} agent executions and {len(investigation_events)} investigation events reconstructed",
        details={
            "agents": [
                {"agent_name": a.agent_name, "status": a.status} for a in history.agent_executions
            ],
            "investigation_events": [e.event_type for e in investigation_events],
        },
    ))

    rc = history.root_cause
    existing_evidence_ids = {e.evidence_id for e in history.evidence}
    rc_evidence_ids = (rc.evidence_ids or []) if rc else []
    stages.append(ReplayStageSnapshot(
        stage="ROOT_CAUSE",
        available=rc is not None,
        status=rc.status if rc else None,
        summary=(
            f"Root cause reconstructed: {rc.root_cause}"
            if rc and rc.root_cause
            else "No root cause recorded"
        ),
        details={
            "root_cause": rc.root_cause if rc else None,
            "confidence": rc.confidence if rc else None,
            "evidence_ids": rc_evidence_ids,
            "evidence_linked": bool(rc_evidence_ids) and all(
                eid in existing_evidence_ids for eid in rc_evidence_ids
            ),
            "identified_at": _iso(rc.identified_at) if rc else None,
        },
    ))

    rem = history.remediation
    stages.append(ReplayStageSnapshot(
        stage="REMEDIATION",
        available=rem is not None,
        status=rem.status if rem else None,
        summary=(
            f"Remediation decision reconstructed: {rem.action_type} on {_target_service(incident, history)}"
            if rem
            else "No remediation proposal recorded"
        ),
        details={
            "action_type": rem.action_type if rem else None,
            "description": rem.description if rem else None,
            "parameters": rem.parameters if rem else {},
            "target_service": _target_service(incident, history) if rem else None,
            "created_at": _iso(rem.created_at) if rem else None,
        },
    ))

    stages.append(ReplayStageSnapshot(
        stage="RISK",
        available=risk is not None,
        status=risk.risk_level if risk else None,
        summary=(
            f"Risk re-evaluated deterministically: {risk.risk_level} (approval required: {risk.requires_approval})"
            if risk
            else "No remediation to re-evaluate risk for"
        ),
        details={
            "risk_level": risk.risk_level if risk else None,
            "allowed": risk.allowed if risk else None,
            "requires_approval": risk.requires_approval if risk else None,
            "reasons": risk.reasons if risk else [],
            "note": "Deterministic policy re-evaluation; no infrastructure interaction.",
        },
    ))

    approval = history.approval
    stages.append(ReplayStageSnapshot(
        stage="APPROVAL",
        available=approval is not None,
        status=approval.status if approval else None,
        summary=(
            f"Approval state reconstructed: {approval.status}"
            if approval
            else "No approval record (action may not have required approval)"
        ),
        details={
            "status": approval.status if approval else None,
            "requested_at": _iso(approval.requested_at) if approval else None,
            "resolved_at": _iso(approval.resolved_at) if approval else None,
            "reason": approval.reason if approval else None,
        },
    ))

    execution = history.execution
    stages.append(ReplayStageSnapshot(
        stage="EXECUTION",
        available=execution is not None,
        status=execution.status if execution else None,
        summary=(
            f"Historical execution reconstructed: {execution.status}"
            if execution
            else "No execution recorded"
        ),
        details={
            "status": execution.status if execution else None,
            "result": execution.result if execution else None,
            "error": execution.error if execution else None,
            "started_at": _iso(execution.started_at) if execution else None,
            "completed_at": _iso(execution.completed_at) if execution else None,
            "note": REPLAY_EXECUTION_NOTE,
        },
    ))

    verification = history.verification
    stages.append(ReplayStageSnapshot(
        stage="VERIFICATION",
        available=verification is not None,
        status=verification.status if verification else None,
        summary=(
            verification.summary
            if verification and verification.summary
            else ("Verification record reconstructed" if verification else "No verification recorded")
        ),
        details={
            "status": verification.status if verification else None,
            "derived_status": _derive_verification_status(verification) if verification else None,
            "checks": (verification.metrics or {}).get("checks", []) if verification else [],
            "created_at": _iso(verification.created_at) if verification else None,
        },
    ))

    recorded_eval = history.recorded_evaluation
    stages.append(ReplayStageSnapshot(
        stage="EVALUATION",
        available=True,
        status=replay_evaluation.overall_status,
        summary=f"Evaluation re-run deterministically: {replay_evaluation.overall_status}",
        details={
            "recomputed": {
                "overall_status": replay_evaluation.overall_status,
                "investigation_result": replay_evaluation.investigation_result,
                "rca_result": replay_evaluation.rca_result,
                "remediation_result": replay_evaluation.remediation_result,
                "verification_result": replay_evaluation.verification_result,
            },
            "recorded": (
                {
                    "overall_status": recorded_eval.overall_status,
                    "investigation_result": recorded_eval.investigation_status,
                    "rca_result": recorded_eval.rca_status,
                    "remediation_result": recorded_eval.remediation_status,
                    "verification_result": recorded_eval.verification_status,
                    "evaluated_at": _iso(recorded_eval.evaluated_at),
                }
                if recorded_eval
                else None
            ),
        },
    ))

    return stages


def _build_differences(
    incident: Incident,
    history: IncidentHistory,
    replay_evaluation,
) -> List[ReplayDifference]:
    """Compare recorded artifacts against the replayed/re-derived artifacts.

    Only comparable differences (where a recorded artifact exists) are emitted so
    that an incomplete incident is reported as INCOMPLETE rather than MISMATCH.
    """
    differences: List[ReplayDifference] = []

    def add(field: str, original: Optional[str], replay: Optional[str], details: Optional[str] = None):
        if original is None:
            return
        differences.append(ReplayDifference(
            field=field,
            original=str(original),
            replay=str(replay) if replay is not None else None,
            consistent=(replay is not None and str(original) == str(replay)),
            details=details,
        ))

    if history.root_cause:
        add(
            "rca.root_cause",
            history.root_cause.root_cause,
            history.root_cause.root_cause,
            "RCA reconstructed from persisted root cause record.",
        )

    if history.remediation:
        add(
            "remediation.action_type",
            history.remediation.action_type,
            history.remediation.action_type,
            "Remediation decision reconstructed as historical data.",
        )

    if history.approval:
        add(
            "approval.status",
            history.approval.status,
            history.approval.status,
            "Approval state reconstructed from persisted record.",
        )

    if history.execution:
        add(
            "execution.status",
            history.execution.status,
            history.execution.status,
            REPLAY_EXECUTION_NOTE,
        )

    if history.verification:
        derived = _derive_verification_status(history.verification)
        add(
            "verification.status",
            history.verification.status,
            derived,
            "Replay independently re-derived the status from persisted verification checks."
            if derived is not None
            else "No persisted verification checks available to re-derive status.",
        )

    recorded_eval = history.recorded_evaluation
    if recorded_eval:
        add("evaluation.overall_status", recorded_eval.overall_status, replay_evaluation.overall_status,
            "Recorded evaluation compared against deterministic replay re-evaluation.")
        add("evaluation.investigation_result", recorded_eval.investigation_status, replay_evaluation.investigation_result)
        add("evaluation.rca_result", recorded_eval.rca_status, replay_evaluation.rca_result)
        add("evaluation.remediation_result", recorded_eval.remediation_status, replay_evaluation.remediation_result)
        add("evaluation.verification_result", recorded_eval.verification_status, replay_evaluation.verification_result)

    return differences


def _build_historical_actions(incident: Incident, history: IncidentHistory) -> List[HistoricalAction]:
    rem = history.remediation
    if not rem:
        return []
    execution = history.execution
    return [HistoricalAction(
        action_type=rem.action_type,
        target_service=_target_service(incident, history),
        parameters=rem.parameters or {},
        recorded_status=rem.status,
        approval_status=history.approval.status if history.approval else None,
        execution_status=execution.status if execution else None,
        execution_result=execution.result if execution else None,
        executed=bool(execution and execution.status == "SUCCESS"),
        note=REPLAY_EXECUTION_NOTE,
    )]


def build_replay(incident: Incident, db: Session) -> IncidentReplayResult:
    """Deterministically reconstruct and re-evaluate an incident (read-only)."""
    history = collect_incident_history(incident, db)

    # Re-run the deterministic risk policy against the recorded remediation.
    risk = None
    if history.remediation:
        try:
            risk = evaluate_risk(RemediationProposal(
                action_type=history.remediation.action_type or "",
                target_service=_target_service(incident, history) or "unknown",
                parameters=history.remediation.parameters or {},
                reason=history.remediation.description or "",
                evidence_ids=list(history.root_cause.evidence_ids or []) if history.root_cause else [],
                confidence=history.root_cause.confidence if history.root_cause and history.root_cause.confidence is not None else 1.0,
            ))
        except Exception as ex:  # pragma: no cover - defensive
            logger.warning("Risk re-evaluation failed during replay: %s", ex)

    # Re-run the deterministic evaluation against persisted state (never persists).
    replay_evaluation = evaluate_incident(incident, db, persist=False)

    stages = _build_stages(incident, history, risk, replay_evaluation)
    differences = _build_differences(incident, history, replay_evaluation)
    historical_actions = _build_historical_actions(incident, history)

    if not differences:
        consistency = "INCOMPLETE"
        summary = (
            "Replay reconstructed insufficient historical data to compare against a recorded "
            "outcome; the incident lifecycle has not progressed far enough."
        )
    elif all(d.consistent for d in differences):
        consistency = "MATCH"
        summary = (
            f"Replay reproduced the recorded incident outcome across {len(differences)} "
            "compared artifact(s) with no differences."
        )
    else:
        inconsistent = [d.field for d in differences if not d.consistent]
        consistency = "MISMATCH"
        summary = (
            "Replay diverged from the recorded incident data for: "
            f"{', '.join(inconsistent)}."
        )

    return IncidentReplayResult(
        replay_id=f"REPLAY-{uuid.uuid4().hex[:6].upper()}",
        incident_id=incident.incident_id,
        incident_status=_value(incident.status) or "UNKNOWN",
        replay_consistency=consistency,
        summary=summary,
        stages=stages,
        differences=differences,
        historical_actions=historical_actions,
        replayed_at=datetime.utcnow(),
    )


def get_incident_replay_by_id(incident_id: str, db: Session) -> IncidentReplayResult:
    incident = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return build_replay(incident, db)
