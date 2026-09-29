from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.all import IncidentStatus, Severity

class IncidentCreate(BaseModel):
    title: str
    description: Optional[str] = None
    severity: Severity
    affected_service: Optional[str] = None
    fault_type: Optional[str] = None

class IncidentResponse(BaseModel):
    id: int
    incident_id: str
    title: str
    description: Optional[str]
    status: IncidentStatus
    severity: Severity
    affected_service: Optional[str]
    fault_type: Optional[str]
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class IncidentEventResponse(BaseModel):
    event_type: str
    source: Optional[str]
    message: Optional[str]
    timestamp: datetime
    metadata_json: Dict[str, Any]

    class Config:
        from_attributes = True

class EvidenceCreate(BaseModel):
    evidence_type: str
    source: str
    service: str
    summary: str
    payload: Dict[str, Any]
    confidence: Optional[float] = None

class EvidenceResponse(EvidenceCreate):
    evidence_id: str
    timestamp: datetime

    class Config:
        from_attributes = True

class ApprovalCreate(BaseModel):
    reason: Optional[str] = None

class ApprovalResponse(BaseModel):
    id: int
    status: str
    requested_at: datetime
    resolved_at: Optional[datetime]
    reason: Optional[str]

    class Config:
        from_attributes = True

class AIInvestigationResponse(BaseModel):
    incident_id: str
    status: str
    timeline: List[str]
    errors: List[str]
    root_cause: Optional[str] = None

class AgentExecutionResponse(BaseModel):
    agent_name: str
    status: str
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class RemediationProposal(BaseModel):
    action_type: str
    target_service: str
    parameters: Dict[str, Any]
    reason: str
    evidence_ids: List[str]
    confidence: float

class RiskAssessment(BaseModel):
    risk_level: str
    allowed: bool
    requires_approval: bool
    reasons: List[str]

class ActionResult(BaseModel):
    success: bool
    execution_id: Optional[str] = None
    action_type: str
    target: str
    previous_state: Optional[Dict[str, Any]] = None
    new_state: Optional[Dict[str, Any]] = None
    message: str
    timestamp: datetime

class VerificationCheck(BaseModel):
    name: str
    passed: bool
    observed: str
    expected: str

class VerificationResult(BaseModel):
    verified: bool
    verification_status: str
    summary: str
    checks: List[VerificationCheck]
    evidence_ids: List[str]
    confidence: float
    timestamp: datetime

class EvaluationCheck(BaseModel):
    name: str
    dimension: str
    passed: bool
    observed: str
    expected: str
    details: Optional[str] = None

class EvaluationResult(BaseModel):
    evaluation_id: str
    incident_id: str
    overall_status: str
    summary: str
    investigation_result: str
    rca_result: str
    remediation_result: str
    verification_result: str
    checks: List[EvaluationCheck]
    failures: List[str]
    recommendations: List[str]
    evaluated_at: datetime

    class Config:
        from_attributes = True

class ReplayStageSnapshot(BaseModel):
    stage: str
    available: bool
    status: Optional[str] = None
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)

class HistoricalAction(BaseModel):
    action_type: str
    target_service: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    recorded_status: Optional[str] = None
    approval_status: Optional[str] = None
    execution_status: Optional[str] = None
    execution_result: Optional[str] = None
    executed: bool = False
    note: str = "Historical record only; replay never executes remediation."

class ReplayDifference(BaseModel):
    field: str
    original: Optional[str] = None
    replay: Optional[str] = None
    consistent: bool
    details: Optional[str] = None

class IncidentReplayResult(BaseModel):
    replay_id: str
    incident_id: str
    incident_status: str
    replay_consistency: str
    summary: str
    stages: List[ReplayStageSnapshot]
    differences: List[ReplayDifference]
    historical_actions: List[HistoricalAction]
    replayed_at: datetime

class PostmortemTimelineEntry(BaseModel):
    timestamp: Optional[datetime] = None
    stage: str
    event: str
    source: Optional[str] = None
    message: Optional[str] = None

class PostmortemSection(BaseModel):
    section: str
    available: bool
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)

class PostmortemResult(BaseModel):
    postmortem_id: str
    incident_id: str
    title: str
    severity: str
    affected_service: Optional[str] = None
    final_status: str
    generated_at: datetime
    summary: str
    impact: str
    timeline: List[PostmortemTimelineEntry]
    sections: List[PostmortemSection]
    lessons: List[str]
