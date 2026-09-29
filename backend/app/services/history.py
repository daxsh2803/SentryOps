from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.all import (
    Incident,
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


@dataclass
class IncidentHistory:
    """Read-only snapshot of the persisted lifecycle for one incident.

    Collecting history must never mutate the database or infrastructure; every
    field is sourced from records already persisted by the incident lifecycle.
    """

    events: List[IncidentEvent] = field(default_factory=list)
    evidence: List[Evidence] = field(default_factory=list)
    agent_executions: List[AgentExecution] = field(default_factory=list)
    root_cause: Optional[RootCause] = None
    remediation: Optional[Remediation] = None
    approval: Optional[Approval] = None
    execution: Optional[Execution] = None
    verification: Optional[Verification] = None
    recorded_evaluation: Optional[Evaluation] = None


def collect_incident_history(incident: Incident, db: Session) -> IncidentHistory:
    """Query the persisted lifecycle records for an incident (no writes)."""
    events = (
        db.query(IncidentEvent)
        .filter(IncidentEvent.incident_id == incident.id)
        .order_by(IncidentEvent.timestamp.asc())
        .all()
    )
    evidence = db.query(Evidence).filter(Evidence.incident_id == incident.id).all()
    agent_executions = (
        db.query(AgentExecution).filter(AgentExecution.incident_id == incident.id).all()
    )
    root_cause = (
        db.query(RootCause)
        .filter(RootCause.incident_id == incident.id)
        .order_by(RootCause.id.desc())
        .first()
    )
    remediation = (
        db.query(Remediation)
        .filter(Remediation.incident_id == incident.id)
        .order_by(Remediation.id.desc())
        .first()
    )
    approval = (
        db.query(Approval).filter(Approval.remediation_id == remediation.id).first()
        if remediation
        else None
    )
    execution = (
        db.query(Execution).filter(Execution.remediation_id == remediation.id).first()
        if remediation
        else None
    )
    verification = (
        db.query(Verification)
        .filter(Verification.incident_id == incident.id)
        .order_by(Verification.id.desc())
        .first()
    )
    recorded_evaluation = (
        db.query(Evaluation)
        .filter(Evaluation.incident_id == incident.id)
        .order_by(Evaluation.id.desc())
        .first()
    )

    return IncidentHistory(
        events=events,
        evidence=evidence,
        agent_executions=agent_executions,
        root_cause=root_cause,
        remediation=remediation,
        approval=approval,
        execution=execution,
        verification=verification,
        recorded_evaluation=recorded_evaluation,
    )
