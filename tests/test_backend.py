import httpx
import pytest

BACKEND_API = "http://localhost:8080"

def test_backend_health():
    r = httpx.get(f"{BACKEND_API}/health")
    assert r.status_code == 200

def test_incident_lifecycle():
    # 1. Create incident
    payload = {
        "title": "Test Incident",
        "description": "Test",
        "severity": "HIGH",
        "affected_service": "payment-service",
        "fault_type": "http_500_spike"
    }
    r = httpx.post(f"{BACKEND_API}/incidents", json=payload)
    assert r.status_code == 200
    incident = r.json()
    assert "incident_id" in incident
    assert incident["status"] == "DETECTED"
    
    inc_id = incident["incident_id"]

    # 2. Get incident details
    r = httpx.get(f"{BACKEND_API}/incidents/{inc_id}")
    assert r.status_code == 200
    assert r.json()["title"] == "Test Incident"

    # 3. Investigate incident
    r = httpx.post(f"{BACKEND_API}/incidents/{inc_id}/investigate")
    assert r.status_code == 200
    assert r.json()["status"] == "INVESTIGATING"

    # 4. Check timeline
    r = httpx.get(f"{BACKEND_API}/incidents/{inc_id}/timeline")
    assert r.status_code == 200
    timeline = r.json()
    assert len(timeline) >= 2
    types = [t["event_type"] for t in timeline]
    assert "INCIDENT_CREATED" in types
    assert "INVESTIGATION_STARTED" in types

    # 5. Add evidence
    ev_payload = {
        "evidence_type": "METRIC",
        "source": "prometheus",
        "service": "payment-service",
        "summary": "High 500s",
        "payload": {},
        "confidence": 0.9
    }
    r = httpx.post(f"{BACKEND_API}/incidents/{inc_id}/evidence", json=ev_payload)
    assert r.status_code == 200

    # 6. Get evidence
    r = httpx.get(f"{BACKEND_API}/incidents/{inc_id}/evidence")
    assert r.status_code == 200
    assert len(r.json()) >= 1

    # 7. Approve / Reject tests
    r = httpx.post(f"{BACKEND_API}/incidents/{inc_id}/approve", json={"reason": "LGTM"})
    assert r.status_code == 200
    assert r.json()["status"] == "APPROVED"

