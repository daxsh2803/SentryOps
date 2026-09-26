from app.ai.state import InvestigationState
from app.db.session import SessionLocal
from app.models.all import KnowledgeChunk, KnowledgeDocument
from app.ai.embeddings import get_embeddings
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

def retrieve_knowledge(
    query: str, 
    db, 
    limit: int = 3, 
    service: Optional[str] = None, 
    doc_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    embeddings = get_embeddings()
    query_vector = embeddings.embed_query(query)
    
    q = db.query(
        KnowledgeChunk, 
        KnowledgeDocument, 
        KnowledgeChunk.embedding.cosine_distance(query_vector).label("distance")
    ).join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
    
    if service:
        q = q.filter(KnowledgeDocument.service == service)
    if doc_type:
        q = q.filter(KnowledgeDocument.doc_type == doc_type)
        
    results = q.order_by("distance").limit(limit).all()
    
    output = []
    for chunk, doc, distance in results:
        dist_val = distance if distance is not None else 0.0
        similarity = 1.0 - dist_val
        output.append({
            "document_id": doc.id,
            "chunk_id": chunk.id,
            "title": doc.title,
            "source": doc.title,
            "doc_type": doc.doc_type,
            "service": doc.service,
            "content": chunk.content,
            "similarity": similarity
        })
    return output

def knowledge_agent_node(state: InvestigationState):
    incident_id = state.get("incident_id")
    context = state.get("incident_context", "")
    service = state.get("affected_service", "")
    fault_type = state.get("fault_type", "")
    evidence = state.get("evidence", [])
    
    # Construct a concise deterministic query from the relevant fields
    query_parts = []
    if service:
        query_parts.append(f"Service: {service}")
    if fault_type:
        query_parts.append(f"Fault: {fault_type}")
    if context:
        query_parts.append(f"Context: {context}")
        
    # Include relevant existing investigation evidence (summarized)
    if evidence:
        evidence_summaries = [e.get("summary") for e in evidence if e.get("summary")]
        if evidence_summaries:
            query_parts.append(f"Evidence: {' | '.join(evidence_summaries)}")
            
    query = " ".join(query_parts)
    
    db = SessionLocal()
    try:
        findings = retrieve_knowledge(query, db, limit=3, service=service)
        
        evidence_id = f"EVID-KNOW-{uuid.uuid4().hex[:4].upper()}"
        
        payload = {"retrieved_docs": findings}
        
        # Calculate a deterministic confidence based on retrieval quality
        confidence = 0.0
        if findings:
            confidence = max((f["similarity"] for f in findings), default=0.0)
            
        ev = {
            "evidence_id": evidence_id,
            "evidence_type": "KNOWLEDGE_RETRIEVAL",
            "source": "knowledge-agent",
            "service": service,
            "summary": f"Retrieved {len(findings)} historical documents/runbooks",
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat(),
            "confidence": confidence
        }
        
        # Format for state
        formatted_findings = []
        for f in findings:
            formatted_findings.append({
                "source": f["title"], 
                "type": f["doc_type"], 
                "content": f["content"],
                "similarity": f["similarity"],
                "chunk_id": f["chunk_id"],
                "document_id": f["document_id"]
            })
        
        return {
            "knowledge_findings": formatted_findings,
            "evidence": [ev],
            "timeline": ["KNOWLEDGE_AGENT: Retrieval completed"]
        }
    except Exception as e:
        return {
            "knowledge_findings": [],
            "errors": [f"KnowledgeAgent Error: {str(e)}"],
            "timeline": ["KNOWLEDGE_AGENT: Error during retrieval"]
        }
    finally:
        db.close()
