from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid
from datetime import datetime

from app.db.session import get_db
from app.models.all import Incident, IncidentEvent, Evidence, Approval, Remediation, IncidentStatus, Severity
from app.schemas.all import IncidentCreate, IncidentResponse, IncidentEventResponse, EvidenceCreate, EvidenceResponse, ApprovalCreate, ApprovalResponse, AgentExecutionResponse

router = APIRouter()

@router.post('/incidents', response_model=IncidentResponse)
def create_incident(incident: IncidentCreate, db: Session = Depends(get_db)):
    incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
    db_incident = Incident(
        incident_id=incident_id,
        title=incident.title,
        description=incident.description,
        severity=incident.severity,
        affected_service=incident.affected_service,
        fault_type=incident.fault_type,
        status=IncidentStatus.DETECTED
    )
    db.add(db_incident)
    db.commit()
    db.refresh(db_incident)

    event = IncidentEvent(
        incident_id=db_incident.id,
        event_type="INCIDENT_CREATED",
        source="incident-api",
        message="Incident created",
        timestamp=datetime.utcnow()
    )
    db.add(event)
    db.commit()

    return db_incident

@router.get('/incidents', response_model=List[IncidentResponse])
def get_incidents(status: str = None, severity: str = None, affected_service: str = None, db: Session = Depends(get_db)):
    query = db.query(Incident)
    if status:
        query = query.filter(Incident.status == status)
    if severity:
        query = query.filter(Incident.severity == severity)
    if affected_service:
        query = query.filter(Incident.affected_service == affected_service)

    return query.all()

@router.get('/incidents/{incident_id}', response_model=IncidentResponse)
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident

@router.get('/incidents/{incident_id}/timeline', response_model=List[IncidentEventResponse])
def get_incident_timeline(incident_id: str, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    events = db.query(IncidentEvent).filter(IncidentEvent.incident_id == incident.id).order_by(IncidentEvent.timestamp.asc()).all()
    return events

@router.get('/incidents/{incident_id}/evidence', response_model=List[EvidenceResponse])
def get_evidence(incident_id: str, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    evidence = db.query(Evidence).filter(Evidence.incident_id == incident.id).order_by(Evidence.timestamp.asc()).all()
    return evidence

@router.get('/incidents/{incident_id}/executions', response_model=List[AgentExecutionResponse])
def get_incident_executions(incident_id: str, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    from app.models.all import AgentExecution
    executions = db.query(AgentExecution).filter(AgentExecution.incident_id == incident.id).order_by(AgentExecution.id.asc()).all()
    return executions

@router.post('/incidents/{incident_id}/evidence', response_model=EvidenceResponse)
def add_evidence(incident_id: str, evidence: EvidenceCreate, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    db_evidence = Evidence(
        incident_id=incident.id,
        evidence_id=f"EVID-{uuid.uuid4().hex[:6].upper()}",
        evidence_type=evidence.evidence_type,
        source=evidence.source,
        service=evidence.service,
        summary=evidence.summary,
        payload=evidence.payload,
        confidence=evidence.confidence,
        timestamp=datetime.utcnow()
    )
    db.add(db_evidence)
    db.commit()
    db.refresh(db_evidence)

    event = IncidentEvent(
        incident_id=incident.id,
        event_type="EVIDENCE_ADDED",
        source="incident-api",
        message=f"Added evidence: {evidence.evidence_type}",
        timestamp=datetime.utcnow()
    )
    db.add(event)
    db.commit()

    return db_evidence

@router.post('/incidents/{incident_id}/investigate')
def investigate_incident(incident_id: str, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    if incident.status == IncidentStatus.RESOLVED or incident.status == IncidentStatus.CLOSED:
        raise HTTPException(status_code=400, detail="Cannot investigate a resolved/closed incident")

    if incident.status == IncidentStatus.INVESTIGATING:
        return {"incident_id": incident.incident_id, "status": incident.status}

    incident.status = IncidentStatus.INVESTIGATING
    incident.updated_at = datetime.utcnow()

    event = IncidentEvent(
        incident_id=incident.id,
        event_type="INVESTIGATION_STARTED",
        source="incident-api",
        message="Incident moved to INVESTIGATING",
        timestamp=datetime.utcnow()
    )

    db.add(incident)
    db.add(event)
    db.commit()

    return {"incident_id": incident.incident_id, "status": incident.status}

@router.post('/incidents/{incident_id}/approve')
def approve_remediation(incident_id: str, payload: ApprovalCreate, db: Session = Depends(get_db)):
    from app.services.remediation import execute_controlled_action
    from app.schemas.all import RemediationProposal
    from app.models.all import Execution

    incident = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    approval = db.query(Approval).filter(Approval.incident_id == incident.id, Approval.status == 'PENDING').first()
    if not approval:
        raise HTTPException(status_code=404, detail="No pending approval found")

    remediation = db.query(Remediation).filter(Remediation.id == approval.remediation_id).first()

    approval.status = "APPROVED"
    approval.resolved_at = datetime.utcnow()
    approval.reason = payload.reason

    # Execute action
    proposal = RemediationProposal(
        action_type=remediation.action_type,
        target_service=remediation.parameters.get("target_service", ""),
        parameters=remediation.parameters,
        reason=remediation.description,
        evidence_ids=[],
        confidence=1.0
    )

    action_result = execute_controlled_action(proposal)

    execution = Execution(
        incident_id=incident.id,
        remediation_id=remediation.id,
        status="SUCCESS" if action_result.success else "FAILED",
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        result=action_result.message
    )
    db.add(execution)
    db.flush()

    event1 = IncidentEvent(
        incident_id=incident.id,
        event_type="APPROVAL_RESOLVED",
        source="incident-api",
        message="Remediation approved",
        timestamp=datetime.utcnow()
    )
    event2 = IncidentEvent(
        incident_id=incident.id,
        event_type="ACTION_EXECUTED",
        source="incident-api",
        message=f"Action execution: {action_result.message}",
        timestamp=datetime.utcnow()
    )
    db.add(event1)
    db.add(event2)

    if action_result.success:
        from app.services.verification import perform_verification
        from app.models.all import Verification

        action_result.execution_id = str(execution.id)
        state_stub = {"action_result": action_result.model_dump(), "evidence": [{"evidence_id": "api-action"}]}
        verif_result = perform_verification(state_stub["action_result"], state_stub)

        verification = Verification(
            incident_id=incident.id,
            execution_id=execution.id,
            status=verif_result.verification_status,
            summary=verif_result.summary,
            metrics={"checks": [c.model_dump() for c in verif_result.checks], "confidence": verif_result.confidence},
            created_at=datetime.utcnow()
        )
        db.add(verification)

        if verif_result.verified:
            incident.status = "RESOLVED"
            event3 = IncidentEvent(
                incident_id=incident.id,
                event_type="INCIDENT_RESOLVED",
                source="incident-api",
                message="Incident verified resolved",
                timestamp=datetime.utcnow()
            )
            db.add(event3)
        else:
            incident.status = "INVESTIGATING"
            event3 = IncidentEvent(
                incident_id=incident.id,
                event_type="INCIDENT_REINVESTIGATION_REQUIRED",
                source="incident-api",
                message="Verification failed, re-investigating",
                timestamp=datetime.utcnow()
            )
            db.add(event3)
        db.add(incident)

    db.commit()

    return {"status": "APPROVED", "remediation_id": approval.remediation_id, "execution_status": execution.status}

@router.post('/incidents/{incident_id}/reject')
def reject_remediation(incident_id: str, payload: ApprovalCreate, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    approval = db.query(Approval).filter(Approval.incident_id == incident.id, Approval.status == 'PENDING').first()
    if not approval:
        raise HTTPException(status_code=404, detail="No pending approval found")

    approval.status = "REJECTED"
    approval.resolved_at = datetime.utcnow()
    approval.reason = payload.reason

    event = IncidentEvent(
        incident_id=incident.id,
        event_type="APPROVAL_RESOLVED",
        source="incident-api",
        message="Remediation rejected",
        timestamp=datetime.utcnow()
    )
    db.add(approval)
    db.add(event)
    db.commit()

    return {"status": "REJECTED", "remediation_id": approval.remediation_id}

@router.get('/incidents/{incident_id}/remediation')
def get_remediation(incident_id: str, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    remediation = db.query(Remediation).filter(Remediation.incident_id == incident.id).order_by(Remediation.id.desc()).first()
    if not remediation:
        return {}

    approval = db.query(Approval).filter(Approval.remediation_id == remediation.id).first()
    from app.models.all import Execution
    execution = db.query(Execution).filter(Execution.remediation_id == remediation.id).first()

    return {
        "remediation": {
            "id": remediation.id,
            "action_type": remediation.action_type,
            "description": remediation.description,
            "status": remediation.status,
            "parameters": remediation.parameters
        },
        "approval": {
            "id": approval.id,
            "status": approval.status
        } if approval else None,
        "execution": {
            "id": execution.id,
            "status": execution.status,
            "result": execution.result
        } if execution else None
    }

@router.get('/incidents/{incident_id}/rca')
def get_rca(incident_id: str, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    from app.models.all import RootCause
    rc = db.query(RootCause).filter(RootCause.incident_id == incident.id).order_by(RootCause.id.desc()).first()
    if not rc:
        return {}
    return {
        "id": rc.id,
        "root_cause": rc.root_cause,
        "confidence": rc.confidence,
        "evidence_ids": rc.evidence_ids,
        "status": rc.status,
        "identified_at": rc.identified_at
    }

@router.get('/incidents/{incident_id}/risk')
def get_risk(incident_id: str, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    remediation = db.query(Remediation).filter(Remediation.incident_id == incident.id).order_by(Remediation.id.desc()).first()
    if not remediation:
        return {}

    from app.services.remediation import evaluate_risk
    from app.schemas.all import RemediationProposal
    proposal = RemediationProposal(
        action_type=remediation.action_type,
        target_service=remediation.parameters.get("target_service", "unknown"),
        parameters=remediation.parameters,
        reason=remediation.description or "",
        evidence_ids=[],
        confidence=1.0
    )
    risk_assessment = evaluate_risk(proposal)
    return risk_assessment.model_dump()

@router.get('/service-health/{service}')
def get_service_health(service: str):
    from app.services.remediation import get_simulated_state
    return get_simulated_state(service)

from app.ai.graph import graph
from app.ai.state import InvestigationState
from app.schemas.all import AIInvestigationResponse
from app.models.all import AgentExecution, RootCause

@router.post('/incidents/{incident_id}/ai-investigate', response_model=AIInvestigationResponse)
def ai_investigate_incident(incident_id: str, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident.status = IncidentStatus.INVESTIGATING
    db.commit()

    initial_state = {
        "incident_id": incident.incident_id,
        "db_incident_id": incident.id,
        "status": incident.status.value,
        "severity": incident.severity.value,
        "affected_service": incident.affected_service or "",
        "fault_type": incident.fault_type or "",
        "incident_context": incident.description or "",
        "investigation_plan": "",
        "log_findings": [],
        "metric_findings": [],
        "trace_findings": [],
        "deployment_findings": [],
        "infrastructure_findings": [],
        "knowledge_findings": [],
        "evidence": [],
        "root_cause": "",
        "root_cause_confidence": 0.0,
        "root_cause_evidence_ids": [],
        "errors": [],
        "timeline": ["AI_INVESTIGATION_STARTED"]
    }

    final_state = graph.invoke(initial_state)
    final_state["timeline"].append("AI_INVESTIGATION_COMPLETED")

    # Persist agent executions based on timeline
    agents_run = [
        "IncidentManager",
        "LogAgent",
        "MetricsAgent",
        "TraceAgent",
        "DeploymentAgent",
        "InfrastructureAgent",
        "KnowledgeAgent",
        "RCAAgent"
    ]
    for agent in agents_run:
        exec_record = AgentExecution(
            incident_id=incident.id,
            agent_name=agent,
            status="COMPLETED",
            input_summary="Triggered by orchestration",
            output_summary=f"Completed {agent} phase"
        )
        db.add(exec_record)

    # Persist evidence
    for ev in final_state.get("evidence", []):
        ev_ts = datetime.utcnow()
        if "timestamp" in ev and ev["timestamp"]:
            try:
                ev_ts = datetime.fromisoformat(ev["timestamp"]) if isinstance(ev["timestamp"], str) else ev["timestamp"]
            except Exception:
                ev_ts = datetime.utcnow()
        db_ev = Evidence(
            incident_id=incident.id,
            evidence_id=ev["evidence_id"],
            evidence_type=ev["evidence_type"],
            source=ev["source"],
            service=ev["service"],
            summary=ev["summary"],
            payload=ev.get("payload", {}),
            confidence=ev.get("confidence"),
            timestamp=ev_ts
        )
        db.add(db_ev)

    # Persist timeline
    for event_str in final_state["timeline"]:
        db_event = IncidentEvent(
            incident_id=incident.id,
            event_type=event_str.split(":")[0],
            source="ai-investigator",
            message=event_str
        )
        db.add(db_event)

    # Persist root cause
    if final_state.get("root_cause"):
        db_rc = RootCause(
            incident_id=incident.id,
            root_cause=final_state["root_cause"],
            confidence=final_state["root_cause_confidence"],
            evidence_ids=final_state["root_cause_evidence_ids"],
            status="IDENTIFIED"
        )
        db.add(db_rc)

    # Persist remediation
    if final_state.get("remediation_proposal"):
        proposal = final_state["remediation_proposal"]
        db_remediation = Remediation(
            incident_id=incident.id,
            action_type=proposal["action_type"],
            description=proposal["reason"],
            status=final_state.get("approval_status", "PENDING_APPROVAL"),
            parameters={**proposal["parameters"], "target_service": proposal["target_service"]}
        )
        db.add(db_remediation)
        db.commit()
        db.refresh(db_remediation)

        if final_state.get("risk_assessment"):
            if final_state["risk_assessment"]["requires_approval"]:
                db_approval = Approval(
                    incident_id=incident.id,
                    remediation_id=db_remediation.id,
                    status=final_state.get("approval_status", "PENDING")
                )
                db.add(db_approval)

        if final_state.get("action_result"):
            from app.models.all import Execution
            res = final_state["action_result"]
            db_exec = Execution(
                incident_id=incident.id,
                remediation_id=db_remediation.id,
                status="SUCCESS" if res["success"] else "FAILED",
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                result=res["message"]
            )
            db.add(db_exec)

    db.commit()

    return AIInvestigationResponse(
        incident_id=incident_id,
        status="INVESTIGATING",
        timeline=final_state["timeline"],
        errors=final_state["errors"],
        root_cause=final_state.get("root_cause")
    )


@router.get('/incidents/{incident_id}/verification')
def get_verification(incident_id: str, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    from app.models.all import Verification
    verification = db.query(Verification).filter(Verification.incident_id == incident.id).order_by(Verification.id.desc()).first()

    if not verification:
        return {}

    return {
        "id": verification.id,
        "execution_id": verification.execution_id,
        "status": verification.status,
        "summary": verification.summary,
        "metrics": verification.metrics,
        "created_at": verification.created_at
    }
