from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import hashlib
from typing import List, Optional

from app.db.session import get_db
from app.models.all import KnowledgeDocument, KnowledgeChunk
from app.ai.embeddings import get_embeddings
from datetime import datetime

router = APIRouter()

class DocumentIngest(BaseModel):
    title: str
    content: str
    doc_type: str
    service: str

class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    service: Optional[str] = None
    doc_type: Optional[str] = None

def chunk_text(text: str, max_length: int = 1000, overlap: int = 200) -> List[str]:
    if not text.strip():
        return [text]
    chunks = []
    start = 0
    text = text.strip()
    while start < len(text):
        end = min(start + max_length, len(text))
        if end < len(text):
            last_double_newline = text.rfind('\n\n', start, end)
            last_newline = text.rfind('\n', start, end)
            last_space = text.rfind(' ', start, end)
            if last_double_newline != -1 and last_double_newline > start + overlap:
                end = last_double_newline + 2
            elif last_newline != -1 and last_newline > start + overlap:
                end = last_newline + 1
            elif last_space != -1 and last_space > start + overlap:
                end = last_space + 1
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - (overlap if end < len(text) else 0)
    if not chunks:
        chunks = [text]
    return chunks

@router.post('/knowledge/ingest')
def ingest_document(doc: DocumentIngest, db: Session = Depends(get_db)):
    # Deterministic document identity
    doc_hash = hashlib.md5(f"{doc.service}:{doc.title}:{doc.content}".encode('utf-8')).hexdigest()[:12].upper()
    doc_id = f"DOC-{doc_hash}"
    
    existing = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id).first()
    if existing:
        return {"doc_id": doc_id, "status": "Skipped (Duplicate)", "chunks_created": 0}
        
    db_doc = KnowledgeDocument(
        id=doc_id,
        title=doc.title,
        content=doc.content,
        doc_type=doc.doc_type,
        service=doc.service,
        created_at=datetime.utcnow()
    )
    db.add(db_doc)
    db.commit()
    
    chunks = chunk_text(doc.content)
    embeddings = get_embeddings()
    vectors = embeddings.embed_documents(chunks)
    
    for i, (chunk_text_str, vector) in enumerate(zip(chunks, vectors)):
        chunk_id = f"CHK-{doc_id}-{i}"
        db_chunk = KnowledgeChunk(
            id=chunk_id,
            document_id=doc_id,
            content=chunk_text_str.strip(),
            embedding=vector,
            chunk_index=i
        )
        db.add(db_chunk)
        
    db.commit()
    
    return {"doc_id": doc_id, "status": "Ingested", "chunks_created": len(chunks)}

@router.post('/knowledge/query')
def query_knowledge(req: QueryRequest, db: Session = Depends(get_db)):
    embeddings = get_embeddings()
    query_vector = embeddings.embed_query(req.query)
    
    q = db.query(KnowledgeChunk, KnowledgeDocument)
    q = q.join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
    
    if req.service:
        q = q.filter(KnowledgeDocument.service == req.service)
    if req.doc_type:
        q = q.filter(KnowledgeDocument.doc_type == req.doc_type)
        
    results = q.order_by(KnowledgeChunk.embedding.cosine_distance(query_vector)).limit(req.top_k).all()
    
    output = []
    for chunk, doc in results:
        # Reconstruct similarity from distance if driver supports it, or use cosine_distance directly.
        # pgvector SQLAlchemy returns a tuple (KnowledgeChunk, KnowledgeDocument), we can fetch distance in a subquery or recompute it/fetch it.
        # Let's execute the distance as an extra column.
        pass
    
    # Better to select distance directly
    q2 = db.query(
        KnowledgeChunk, 
        KnowledgeDocument, 
        KnowledgeChunk.embedding.cosine_distance(query_vector).label("distance")
    ).join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
    
    if req.service:
        q2 = q2.filter(KnowledgeDocument.service == req.service)
    if req.doc_type:
        q2 = q2.filter(KnowledgeDocument.doc_type == req.doc_type)
        
    results2 = q2.order_by("distance").limit(req.top_k).all()
    
    output = []
    for chunk, doc, distance in results2:
        similarity = 1.0 - (distance if distance is not None else 0.0)
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
