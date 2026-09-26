from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, JSON, Enum
from sqlalchemy.orm import relationship
import enum
from datetime import datetime
import uuid
from pgvector.sqlalchemy import Vector
from app.db.session import Base

class IncidentStatus(str, enum.Enum):
    DETECTED = 'DETECTED'
    INVESTIGATING = 'INVESTIGATING'
    MITIGATING = 'MITIGATING'
    VERIFYING = 'VERIFYING'
    RESOLVED = 'RESOLVED'
    FAILED = 'FAILED'
    CLOSED = 'CLOSED'

class Severity(str, enum.Enum):
    LOW = 'LOW'
    MEDIUM = 'MEDIUM'
    HIGH = 'HIGH'
    CRITICAL = 'CRITICAL'

class Incident(Base):
    __tablename__ = 'incidents'
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    description = Column(String)
    status = Column(Enum(IncidentStatus), default=IncidentStatus.DETECTED, nullable=False, index=True)
    severity = Column(Enum(Severity), nullable=False)
    affected_service = Column(String, index=True)
    fault_type = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = Column(DateTime)
    resolved_at = Column(DateTime)
    
    events = relationship('IncidentEvent', back_populates='incident')
    evidence = relationship('Evidence', back_populates='incident')
    root_causes = relationship('RootCause', back_populates='incident')
    remediations = relationship('Remediation', back_populates='incident')

class IncidentEvent(Base):
    __tablename__ = 'incident_events'
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey('incidents.id'), nullable=False)
    event_type = Column(String, nullable=False)
    source = Column(String)
    message = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    metadata_json = Column(JSON, default=dict)
    
    incident = relationship('Incident', back_populates='events')

class Evidence(Base):
    __tablename__ = 'evidence'
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey('incidents.id'), nullable=False)
    evidence_id = Column(String, unique=True, index=True, nullable=False)
    evidence_type = Column(String)
    source = Column(String)
    service = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    summary = Column(String)
    payload = Column(JSON, default=dict)
    confidence = Column(Float)
    
    incident = relationship('Incident', back_populates='evidence')

class AgentExecution(Base):
    __tablename__ = 'agent_executions'
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey('incidents.id'), nullable=False)
    agent_name = Column(String)
    status = Column(String)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    input_summary = Column(String)
    output_summary = Column(String)
    error = Column(String)
    metadata_json = Column(JSON, default=dict)

class RootCause(Base):
    __tablename__ = 'root_causes'
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey('incidents.id'), nullable=False)
    root_cause = Column(String)
    confidence = Column(Float)
    evidence_ids = Column(JSON, default=list)
    identified_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String)
    
    incident = relationship('Incident', back_populates='root_causes')

class Remediation(Base):
    __tablename__ = 'remediations'
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey('incidents.id'), nullable=False)
    action_type = Column(String)
    description = Column(String)
    status = Column(String)
    parameters = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    incident = relationship('Incident', back_populates='remediations')
    approvals = relationship('Approval', back_populates='remediation')
    executions = relationship('Execution', back_populates='remediation')

class Approval(Base):
    __tablename__ = 'approvals'
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey('incidents.id'), nullable=False)
    remediation_id = Column(Integer, ForeignKey('remediations.id'), nullable=False)
    status = Column(String, default='PENDING')
    requested_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime)
    reason = Column(String)
    
    remediation = relationship('Remediation', back_populates='approvals')

class Execution(Base):
    __tablename__ = 'executions'
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey('incidents.id'), nullable=False)
    remediation_id = Column(Integer, ForeignKey('remediations.id'), nullable=False)
    status = Column(String, default='PENDING')
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    result = Column(String)
    error = Column(String)
    
    remediation = relationship('Remediation', back_populates='executions')

class Verification(Base):
    __tablename__ = 'verifications'
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey('incidents.id'), nullable=False)
    execution_id = Column(Integer, ForeignKey('executions.id'), nullable=False)
    status = Column(String, default='PENDING')
    summary = Column(String)
    metrics = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

class KnowledgeDocument(Base):
    __tablename__ = 'knowledge_documents'
    id = Column(String, primary_key=True, index=True)
    title = Column(String)
    content = Column(String)
    doc_type = Column(String)
    service = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    chunks = relationship('KnowledgeChunk', back_populates='document')

class KnowledgeChunk(Base):
    __tablename__ = 'knowledge_chunks'
    id = Column(String, primary_key=True, index=True)
    document_id = Column(String, ForeignKey('knowledge_documents.id'), nullable=False)
    content = Column(String)
    embedding = Column(Vector(384))
    chunk_index = Column(Integer)
    document = relationship('KnowledgeDocument', back_populates='chunks')
