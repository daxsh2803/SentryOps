import httpx
import pytest
import os
import uuid

BACKEND_API = "http://127.0.0.1:8080"
MOCK_LLM = os.environ.get("MOCK_LLM", "true")

def test_ai_investigate():
    # 1. Create incident
    payload = {
        "title": "Payment service failure",
        "description": "500 spikes detected",
        "severity": "HIGH",
        "affected_service": "payment-service",
        "fault_type": "http_500_spike"
    }
    r = httpx.post(f"{BACKEND_API}/incidents", json=payload)
    assert r.status_code == 200, r.text
    incident = r.json()
    inc_id = incident["incident_id"]

    # 2. Start AI Investigation
    # The MOCK_LLM is true by default, and Loki/Prometheus might fail to return data, 
    # but the workflow should gracefully handle missing data and complete the graph.
    r = httpx.post(f"{BACKEND_API}/incidents/{inc_id}/ai-investigate")
    assert r.status_code == 200, r.text
    result = r.json()
    
    assert result["status"] == "INVESTIGATING"
    assert "Mocked Root Cause" in result["root_cause"] or "Failed to generate RCA" in result["root_cause"]
    
    # 3. Check timeline persistence
    r = httpx.get(f"{BACKEND_API}/incidents/{inc_id}/timeline")
    timeline = r.json()
    events = [t["event_type"] for t in timeline]
    assert "AI_INVESTIGATION_STARTED" in events
    assert "AGENT_STARTED" in events
    assert "AGENT_COMPLETED" in events
    assert "AI_INVESTIGATION_COMPLETED" in events
