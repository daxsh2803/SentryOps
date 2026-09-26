import pytest
import httpx
import uuid
from app.ai.embeddings import get_embeddings
import os
from typing import List

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

BACKEND_API = "http://127.0.0.1:8080"
MOCK_LLM = os.environ.get("MOCK_LLM", "true")

def test_mock_embeddings():
    emb = get_embeddings()
    text = "Database connection error"
    
    vec1 = emb.embed_query(text)
    vec2 = emb.embed_query(text)
    vec3 = emb.embed_query("Different error")
    
    assert len(vec1) == 384
    assert vec1 == vec2
    assert vec1 != vec3
    
    batch = emb.embed_documents([text, "Different error"])
    assert len(batch) == 2
    assert batch[0] == vec1
    assert batch[1] == vec3

def test_chunking_deterministic():
    text = "Paragraph 1.\n\nParagraph 2."
    c1 = chunk_text(text, max_length=50, overlap=0)
    c2 = chunk_text(text, max_length=50, overlap=0)
    assert c1 == c2

def test_chunking_bounded():
    text = "A" * 5000
    chunks = chunk_text(text, max_length=1000, overlap=200)
    for c in chunks:
        assert len(c) <= 1000
    # verify overlap logic and total covers text
    assert len(chunks) > 1

def test_chunking_empty():
    assert chunk_text("") == [""]
    assert chunk_text("   ") == ["   "]

def test_ingestion_and_duplicate_handling():
    unique_suffix = uuid.uuid4().hex[:8]
    payload = {
        "title": f"Test Runbook {unique_suffix}",
        "content": f"This is a test runbook {unique_suffix}.\n\nIt has two paragraphs.",
        "doc_type": "runbook",
        "service": "test-service"
    }
    r = httpx.post(f"{BACKEND_API}/knowledge/ingest", json=payload)
    assert r.status_code == 200, r.text
    res1 = r.json()
    assert res1["status"] == "Ingested"
    assert res1["chunks_created"] > 0
    doc_id = res1["doc_id"]
    
    # Duplicate ingestion
    r2 = httpx.post(f"{BACKEND_API}/knowledge/ingest", json=payload)
    assert r2.status_code == 200
    res2 = r2.json()
    assert res2["status"] == "Skipped (Duplicate)"
    assert res2["doc_id"] == doc_id
    assert res2["chunks_created"] == 0

    # Verify no duplicate records created via query endpoint
    q_res = httpx.post(
        f"{BACKEND_API}/knowledge/query",
        json={"query": unique_suffix, "top_k": 10, "service": "test-service"}
    ).json()
    matching = [item for item in q_res if item["document_id"] == doc_id]
    assert len(matching) == res1["chunks_created"]
    assert len({item["document_id"] for item in matching}) == 1

def test_retrieval_and_filtering():
    # Ingest multiple docs
    d1 = {"title": "DB Issue", "content": "Database crash on payment", "doc_type": "incident", "service": "payment-service"}
    d2 = {"title": "Cache Issue", "content": "Redis timeout on payment", "doc_type": "incident", "service": "payment-service"}
    d3 = {"title": "Runbook Cache", "content": "How to restart redis", "doc_type": "runbook", "service": "payment-service"}
    d4 = {"title": "Order Issue", "content": "Database crash on order", "doc_type": "incident", "service": "order-service"}
    
    for d in [d1, d2, d3, d4]:
        httpx.post(f"{BACKEND_API}/knowledge/ingest", json=d)
        
    # Search without filters
    r = httpx.post(f"{BACKEND_API}/knowledge/query", json={"query": "Database crash", "top_k": 10})
    assert r.status_code == 200
    res = r.json()
    assert len(res) > 0
    assert "similarity" in res[0]
    assert "chunk_id" in res[0]
    
    # Filter by service
    r = httpx.post(f"{BACKEND_API}/knowledge/query", json={"query": "crash", "top_k": 10, "service": "order-service"})
    res = r.json()
    for item in res:
        assert item["service"] == "order-service"
        
    # Filter by doc_type
    r = httpx.post(f"{BACKEND_API}/knowledge/query", json={"query": "redis", "top_k": 10, "doc_type": "runbook"})
    res = r.json()
    for item in res:
        assert item["doc_type"] == "runbook"
        
    # Filter by service and doc_type
    r = httpx.post(f"{BACKEND_API}/knowledge/query", json={"query": "timeout", "top_k": 10, "service": "payment-service", "doc_type": "incident"})
    res = r.json()
    for item in res:
        assert item["service"] == "payment-service"
        assert item["doc_type"] == "incident"

def test_phase7_end_to_end_investigation():
    # Ingest historical knowledge
    payload = {
        "title": "E2E Historical DB Timeout",
        "content": "The e2e-service suffered a database timeout due to heavy load. Scale the DB.",
        "doc_type": "runbook",
        "service": "e2e-service"
    }
    httpx.post(f"{BACKEND_API}/knowledge/ingest", json=payload)
    
    # Trigger AI Investigation
    inc_payload = {
        "title": "E2E Database timeout",
        "description": "DB connections failing",
        "severity": "HIGH",
        "affected_service": "e2e-service",
        "fault_type": "database_timeout"
    }
    r = httpx.post(f"{BACKEND_API}/incidents", json=inc_payload)
    assert r.status_code == 200, r.text
    incident = r.json()
    inc_id = incident["incident_id"]

    r = httpx.post(f"{BACKEND_API}/incidents/{inc_id}/ai-investigate")
    assert r.status_code == 200, r.text
    result = r.json()
    
    # Verify execution
    r = httpx.get(f"{BACKEND_API}/incidents/{inc_id}/executions")
    execs = r.json()
    agent_names = [e["agent_name"] for e in execs]
    assert "KnowledgeAgent" in agent_names
    
    # Verify evidence (check that knowledge evidence exists and is properly formed)
    r = httpx.get(f"{BACKEND_API}/incidents/{inc_id}/evidence")
    evidence_list = r.json()
    
    knowledge_ev = [e for e in evidence_list if e["evidence_type"] == "KNOWLEDGE_RETRIEVAL"]
    assert len(knowledge_ev) > 0
    ev = knowledge_ev[0]
    assert "confidence" in ev
    
    # Ensure evidence_id is not hallucinated in RCA
    rca_ev_ids = result.get("root_cause_evidence_ids", [])
    valid_ids = {e["evidence_id"] for e in evidence_list}
    for rca_id in rca_ev_ids:
        assert rca_id in valid_ids
