from typing import TypedDict, List, Dict, Any, Annotated
import operator

class InvestigationState(TypedDict):
    incident_id: str
    db_incident_id: int
    status: str
    severity: str
    affected_service: str
    fault_type: str
    incident_context: str
    
    investigation_plan: str
    
    log_findings: List[Dict[str, Any]]
    metric_findings: List[Dict[str, Any]]
    
    evidence: Annotated[List[Dict[str, Any]], operator.add]
    errors: Annotated[List[str], operator.add]
    timeline: Annotated[List[str], operator.add]
    
    root_cause: str
    root_cause_confidence: float
    root_cause_evidence_ids: List[str]
