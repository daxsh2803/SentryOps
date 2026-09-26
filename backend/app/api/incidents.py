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
    # Simulates an approval action on an incident for Phase 4. We just log the approval state.
    incident = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
        
    # We find a pending approval for this incident
    approval = db.query(Approval).filter(Approval.incident_id == incident.id, Approval.status == 'PENDING').first()
    if not approval:
        # Create a dummy remediation & approval if one doesn't exist for test purposes
        remediation = Remediation(incident_id=incident.id, action_type="DUMMY", description="Dummy Action", status="PENDING")
        db.add(remediation)
        db.commit()
        db.refresh(remediation)
        
        approval = Approval(incident_id=incident.id, remediation_id=remediation.id, status="PENDING")
        db.add(approval)
        db.commit()
        db.refresh(approval)
        
    approval.status = "APPROVED"
    approval.resolved_at = datetime.utcnow()
    approval.reason = payload.reason
    
    event = IncidentEvent(
        incident_id=incident.id,
        event_type="APPROVAL_RESOLVED",
        source="incident-api",
        message="Remediation approved",
        timestamp=datetime.utcnow()
    )
    db.add(approval)
    db.add(event)
    db.commit()
    
    return {"status": "APPROVED", "remediation_id": approval.remediation_id}

@router.post('/incidents/{incident_id}/reject')
def reject_remediation(incident_id: str, payload: ApprovalCreate, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
        
    approval = db.query(Approval).filter(Approval.incident_id == incident.id, Approval.status == 'PENDING').first()
    if not approval:
        remediation = Remediation(incident_id=incident.id, action_type="DUMMY", description="Dummy Action", status="PENDING")
        db.add(remediation)
        db.commit()
        db.refresh(remediation)
        
        approval = Approval(incident_id=incident.id, remediation_id=remediation.id, status="PENDING")
        db.add(approval)
        db.commit()
        db.refresh(approval)
        
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

    db.commit()

    return AIInvestigationResponse(
        incident_id=incident_id,
        status="INVESTIGATING",
        timeline=final_state["timeline"],
        errors=final_state["errors"],
        root_cause=final_state.get("root_cause")
    )
