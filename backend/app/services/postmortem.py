"""Phase 12 — deterministic postmortem generation.

A postmortem is assembled entirely from persisted incident records. No LLM is
required for correctness, no timestamp is invented, and the operation is
read-only. Timestamps come only from records that already carry them; where a
record has no timestamp the timeline entry honestly reports ``timestamp=None``.
"""

from typing import Any, List, Optional
import uuid
import logging
from datetime import datetime

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.all import Incident
from app.schemas.all import (
    PostmortemResult,
    PostmortemSection,
    PostmortemTimelineEntry,
    RemediationProposal,
)
from app.services.history import collect_incident_history, IncidentHistory
from app.services.evaluation import evaluate_incident
from app.services.remediation import evaluate_risk

logger = logging.getLogger(__name__)


def _value(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    return raw.value if hasattr(raw, "value") else str(raw)


def _stage_for_event(event_type: Optional[str]) -> str:
    et = (event_type or "").upper()
    if "CREATED" in et or "DETECT" in et:
        return "DETECTION"
    if "INVESTIGAT" in et:
        return "INVESTIGATION"
    if "EVIDENCE" in et:
        return "EVIDENCE"
    if "ROOT_CAUSE" in et or "RCA" in et:
        return "ROOT_CAUSE"
    if "REMEDIATION" in et or "PROPOS" in et:
        return "REMEDIATION"
    if "APPROVAL" in et:
        return "APPROVAL"
    if "ACTION" in et or "EXECUT" in et:
        return "EXECUTION"
    if "VERIF" in et:
        return "VERIFICATION"
    if "EVALUAT" in et:
        return "EVALUATION"
    if "RESOLVED" in et or "RESOLUTION" in et or "REINVESTIGATION" in et:
        return "RESOLUTION"
    return "LIFECYCLE"


def _build_timeline(history: IncidentHistory) -> List[PostmortemTimelineEntry]:
    """Reconstruct the incident timeline from persisted timestamps only."""
    entries: List[PostmortemTimelineEntry] = []
    seen = set()

    for e in history.events:
        key = ("event", e.event_type, e.timestamp, e.message)
        if key in seen:
            continue
        seen.add(key)
        entries.append(PostmortemTimelineEntry(
            timestamp=e.timestamp,
            stage=_stage_for_event(e.event_type),
            event=e.event_type or "EVENT",
            source=e.source,
            message=e.message,
        ))

    def marker(timestamp, stage, event, source, message):
        key = ("marker", event, timestamp)
        if timestamp is None and key in seen:
            return
        seen.add(key)
        entries.append(PostmortemTimelineEntry(
            timestamp=timestamp,
            stage=stage,
            event=event,
            source=source,
            message=message,
        ))

    rc = history.root_cause
    if rc:
        marker(rc.identified_at, "ROOT_CAUSE", "ROOT_CAUSE_IDENTIFIED", "rca-record",
               "Root cause recorded for the incident")

    rem = history.remediation
    if rem:
        marker(rem.created_at, "REMEDIATION", "REMEDIATION_PROPOSED", "remediation-record",
               f"Remediation proposed: {rem.action_type}")

    approval = history.approval
    if approval:
        marker(approval.requested_at, "APPROVAL", "APPROVAL_REQUESTED", "approval-record",
               "Operator approval requested")
        marker(approval.resolved_at, "APPROVAL", f"APPROVAL_{_value(approval.status)}", "approval-record",
               f"Approval resolved with status {_value(approval.status)}")

    execution = history.execution
    if execution:
        marker(execution.started_at, "EXECUTION", "EXECUTION_STARTED", "execution-record",
               "Controlled action execution started (historical)")
        marker(execution.completed_at, "EXECUTION", "EXECUTION_COMPLETED", "execution-record",
               f"Controlled action execution finished with status {_value(execution.status)} (historical)")

    verification = history.verification
    if verification:
        marker(verification.created_at, "VERIFICATION", "VERIFICATION_PERFORMED", "verification-record",
               f"Verification performed with status {_value(verification.status)}")

    recorded_eval = history.recorded_evaluation
    if recorded_eval:
        marker(recorded_eval.evaluated_at, "EVALUATION", "EVALUATION_PERFORMED", "evaluation-record",
               f"Evaluation recorded with status {_value(recorded_eval.overall_status)}")

    # Entries without a timestamp are kept but sorted last, never fabricated.
    entries.sort(key=lambda entry: (entry.timestamp is None, entry.timestamp or datetime.min))
    return entries


def _build_sections(
    incident: Incident,
    history: IncidentHistory,
    risk,
    evaluation,
) -> List[PostmortemSection]:
    sections: List[PostmortemSection] = []

    detection_events = [e for e in history.events if _stage_for_event(e.event_type) == "DETECTION"]
    sections.append(PostmortemSection(
        section="DETECTION",
        available=bool(incident.created_at or detection_events),
        summary=(
            f"Incident detected as '{incident.title}' ({_value(incident.severity)}) "
            f"affecting {incident.affected_service or 'unknown service'}"
            if incident.created_at or detection_events
            else "No detection information recorded."
        ),
        details={
            "created_at": incident.created_at.isoformat() if incident.created_at else None,
            "fault_type": incident.fault_type,
            "detection_events": [e.event_type for e in detection_events],
        },
    ))

    failed_agents = [a.agent_name for a in history.agent_executions if a.status == "FAILED" or a.error]
    sections.append(PostmortemSection(
        section="INVESTIGATION",
        available=bool(history.agent_executions),
        summary=(
            f"{len(history.agent_executions)} agent execution(s) recorded; "
            f"{len(failed_agents)} failed"
            if history.agent_executions
            else "No AI investigation agent executions recorded."
        ),
        details={
            "agent_executions": [
                {"agent_name": a.agent_name, "status": a.status,
                 "started_at": a.started_at.isoformat() if a.started_at else None,
                 "completed_at": a.completed_at.isoformat() if a.completed_at else None}
                for a in history.agent_executions
            ],
            "failed_agents": failed_agents,
        },
    ))

    sections.append(PostmortemSection(
        section="EVIDENCE",
        available=len(history.evidence) > 0,
        summary=(
            f"{len(history.evidence)} evidence item(s) collected"
            if history.evidence
            else "No evidence was collected during the incident."
        ),
        details={
            "count": len(history.evidence),
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

    rc = history.root_cause
    sections.append(PostmortemSection(
        section="ROOT_CAUSE",
        available=rc is not None,
        summary=(
            f"Root cause: {rc.root_cause}"
            if rc and rc.root_cause
            else "No root cause was recorded."
        ),
        details={
            "root_cause": rc.root_cause if rc else None,
            "confidence": rc.confidence if rc else None,
            "evidence_ids": (rc.evidence_ids or []) if rc else [],
            "identified_at": rc.identified_at.isoformat() if rc and rc.identified_at else None,
        },
    ))

    rem = history.remediation
    sections.append(PostmortemSection(
        section="REMEDIATION",
        available=rem is not None,
        summary=(
            f"Proposed action {rem.action_type}"
            + (f" (risk {risk.risk_level})" if risk else "")
            if rem
            else "No remediation was proposed."
        ),
        details={
            "action_type": rem.action_type if rem else None,
            "description": rem.description if rem else None,
            "parameters": rem.parameters if rem else {},
            "recorded_status": rem.status if rem else None,
            "risk": (
                {
                    "risk_level": risk.risk_level,
                    "allowed": risk.allowed,
                    "requires_approval": risk.requires_approval,
                    "reasons": risk.reasons,
                }
                if risk
                else None
            ),
        },
    ))

    approval = history.approval
    if approval:
        approval_summary = f"Approval {approval.status}"
    elif rem is not None and risk is not None and not risk.requires_approval:
        approval_summary = "Approval not required (low risk action)"
    elif rem is not None:
        approval_summary = "No approval record found"
    else:
        approval_summary = "Approval stage not reached."
    sections.append(PostmortemSection(
        section="APPROVAL",
        available=approval is not None,
        summary=approval_summary,
        details={
            "status": approval.status if approval else None,
            "requested_at": approval.requested_at.isoformat() if approval and approval.requested_at else None,
            "resolved_at": approval.resolved_at.isoformat() if approval and approval.resolved_at else None,
            "reason": approval.reason if approval else None,
        },
    ))

    execution = history.execution
    sections.append(PostmortemSection(
        section="EXECUTION",
        available=execution is not None,
        summary=(
            f"Historical execution status: {execution.status} ({execution.result or 'no result detail'})"
            if execution
            else "No controlled action was executed."
        ),
        details={
            "status": execution.status if execution else None,
            "result": execution.result if execution else None,
            "error": execution.error if execution else None,
            "started_at": execution.started_at.isoformat() if execution and execution.started_at else None,
            "completed_at": execution.completed_at.isoformat() if execution and execution.completed_at else None,
            "note": "Historical record only; the postmortem does not re-execute actions.",
        },
    ))

    verification = history.verification
    v_checks = (verification.metrics or {}).get("checks", []) if verification else []
    sections.append(PostmortemSection(
        section="VERIFICATION",
        available=verification is not None,
        summary=(
            verification.summary
            if verification and verification.summary
            else ("Verification record present" if verification else "No verification was performed.")
        ),
        details={
            "status": verification.status if verification else None,
            "checks": v_checks,
            "created_at": verification.created_at.isoformat() if verification and verification.created_at else None,
        },
    ))

    recorded_eval = history.recorded_evaluation
    sections.append(PostmortemSection(
        section="EVALUATION",
        available=True,
        summary=f"Re-evaluated deterministically: {evaluation.overall_status}",
        details={
            "recomputed": {
                "overall_status": evaluation.overall_status,
                "investigation_result": evaluation.investigation_result,
                "rca_result": evaluation.rca_result,
                "remediation_result": evaluation.remediation_result,
                "verification_result": evaluation.verification_result,
                "recommendations": evaluation.recommendations,
                "failures": evaluation.failures,
            },
            "recorded": (
                {
                    "overall_status": recorded_eval.overall_status,
                    "investigation_result": recorded_eval.investigation_status,
                    "rca_result": recorded_eval.rca_status,
                    "remediation_result": recorded_eval.remediation_status,
                    "verification_result": recorded_eval.verification_status,
                    "evaluated_at": recorded_eval.evaluated_at.isoformat() if recorded_eval.evaluated_at else None,
                }
                if recorded_eval
                else None
            ),
        },
    ))

    return sections


def _build_lessons(
    incident: Incident,
    history: IncidentHistory,
    evaluation,
) -> List[str]:
    """Deterministic lessons/recommendations derived from persisted facts."""
    lessons: List[str] = list(evaluation.recommendations)

    if not history.evidence:
        lessons.append("No telemetry evidence was captured; improve observability instrumentation for this service.")
    if history.root_cause is None:
        lessons.append("Root cause was never established; ensure the investigation stage completes for similar incidents.")
    if history.remediation is not None and history.verification is None:
        lessons.append("Remediation was proposed without a verification record; always verify recovery before closure.")
    if history.verification is not None and _value(history.verification.status) != "VERIFIED_SUCCESS":
        lessons.append("Post-remediation verification did not confirm recovery; strengthen rollback and re-investigation playbooks.")

    final_status = _value(incident.status)
    if final_status not in {"RESOLVED", "CLOSED"}:
        lessons.append("Incident is not resolved yet; complete remediation and verification before closing the postmortem.")
    elif evaluation.overall_status == "PASS":
        lessons.append("Response followed the controlled lifecycle successfully; retain this postmortem as a reference runbook.")

    # Preserve deterministic order while removing duplicates.
    deduped: List[str] = []
    for lesson in lessons:
        if lesson not in deduped:
            deduped.append(lesson)
    return deduped


def _build_impact(incident: Incident) -> str:
    service = incident.affected_service or "unknown service"
    start = incident.started_at or incident.created_at
    if incident.resolved_at and start:
        duration = incident.resolved_at - start
        duration_text = f"{int(duration.total_seconds())}s"
    elif incident.resolved_at:
        duration_text = "unknown (no start timestamp recorded)"
    else:
        duration_text = "ongoing / not yet resolved"
    return (
        f"Severity {_value(incident.severity)} impact on {service}. "
        f"Duration: {duration_text}. Fault type: {incident.fault_type or 'unspecified'}."
    )


def _build_summary(incident: Incident, history: IncidentHistory, evaluation) -> str:
    parts = [
        f"{incident.incident_id} ({_value(incident.severity)}) on {incident.affected_service or 'unknown service'}: {incident.title}."
    ]
    if history.root_cause and history.root_cause.root_cause:
        parts.append(f"Root cause: {history.root_cause.root_cause}.")
    if history.remediation:
        outcome = history.execution.status if history.execution else "not executed"
        parts.append(f"Remediation {history.remediation.action_type} was recorded with outcome {outcome}.")
    if history.verification:
        parts.append(f"Verification recorded status {_value(history.verification.status)}.")
    parts.append(f"Overall evaluation: {evaluation.overall_status}.")
    parts.append(f"Final incident status: {_value(incident.status)}.")
    return " ".join(parts)


def build_postmortem(incident: Incident, db: Session) -> PostmortemResult:
    """Deterministically assemble a postmortem from persisted incident data (read-only)."""
    history = collect_incident_history(incident, db)

    risk = None
    if history.remediation:
        try:
            risk = evaluate_risk(RemediationProposal(
                action_type=history.remediation.action_type or "",
                target_service=(
                    (history.remediation.parameters or {}).get("target_service")
                    or incident.affected_service
                    or "unknown"
                ),
                parameters=history.remediation.parameters or {},
                reason=history.remediation.description or "",
                evidence_ids=list(history.root_cause.evidence_ids or []) if history.root_cause else [],
                confidence=history.root_cause.confidence if history.root_cause and history.root_cause.confidence is not None else 1.0,
            ))
        except Exception as ex:  # pragma: no cover - defensive
            logger.warning("Risk re-evaluation failed during postmortem: %s", ex)

    evaluation = evaluate_incident(incident, db, persist=False)

    return PostmortemResult(
        postmortem_id=f"PM-{uuid.uuid4().hex[:6].upper()}",
        incident_id=incident.incident_id,
        title=incident.title,
        severity=_value(incident.severity) or "UNKNOWN",
        affected_service=incident.affected_service,
        final_status=_value(incident.status) or "UNKNOWN",
        generated_at=datetime.utcnow(),
        summary=_build_summary(incident, history, evaluation),
        impact=_build_impact(incident),
        timeline=_build_timeline(history),
        sections=_build_sections(incident, history, risk, evaluation),
        lessons=_build_lessons(incident, history, evaluation),
    )


def get_incident_postmortem_by_id(incident_id: str, db: Session) -> PostmortemResult:
    incident = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return build_postmortem(incident, db)
