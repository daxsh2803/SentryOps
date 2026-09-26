import httpx
import pytest
import time

FAULT_API = "http://127.0.0.1:8005"
PAYMENT_API = "http://127.0.0.1:8002"
ORDER_API = "http://127.0.0.1:8000"

def test_fault_registry():
    r = httpx.get(f"{FAULT_API}/faults/types")
    assert r.status_code == 200
    types = r.json()
    expected = [
        "payment_service_crash", 
        "http_500_spike", 
        "artificial_latency", 
        "db_connection_exhaustion", 
        "bad_configuration"
    ]
    for t in expected:
        assert t in types

def test_inject_and_cleanup_crash():
    # Inject
    payload = {
        "fault_type": "payment_service_crash",
        "target_service": "payment-service",
        "parameters": {}
    }
    r = httpx.post(f"{FAULT_API}/faults/inject", json=payload)
    assert r.status_code == 200
    fault = r.json()
    assert fault["status"] == "ACTIVE"
    fault_id = fault["fault_id"]

    # Verify inspection
    r = httpx.get(f"{FAULT_API}/faults/{fault_id}")
    assert r.status_code == 200
    assert r.json()["ground_truth_root_cause"] == "payment-service unavailable"

    # Verify payment service fails
    # Give Redis a moment to sync
    time.sleep(0.1)
    pr = httpx.post(f"{PAYMENT_API}/pay", json={"amount": 100})
    assert pr.status_code == 503

    # Stop fault
    r = httpx.post(f"{FAULT_API}/faults/{fault_id}/stop")
    assert r.status_code == 200

    # Cleanup
    r = httpx.post(f"{FAULT_API}/faults/{fault_id}/cleanup")
    assert r.status_code == 200

    # Verify recovery
    pr = httpx.post(f"{PAYMENT_API}/pay", json={"amount": 100})
    assert pr.status_code == 200

def test_artificial_latency():
    # Inject
    payload = {
        "fault_type": "artificial_latency",
        "target_service": "payment-service",
        "parameters": {"delay_ms": 1000}
    }
    r = httpx.post(f"{FAULT_API}/faults/inject", json=payload)
    fault_id = r.json()["fault_id"]
    
    time.sleep(0.1)
    
    start_time = time.time()
    pr = httpx.post(f"{PAYMENT_API}/pay", json={"amount": 100})
    duration = time.time() - start_time
    assert pr.status_code == 200
    assert duration >= 1.0
    
    httpx.post(f"{FAULT_API}/faults/{fault_id}/cleanup")

def test_http_500_spike():
    payload = {
        "fault_type": "http_500_spike",
        "target_service": "payment-service",
        "parameters": {"error_rate": 1.0} # 100% fail
    }
    r = httpx.post(f"{FAULT_API}/faults/inject", json=payload)
    fault_id = r.json()["fault_id"]
    
    time.sleep(0.1)
    pr = httpx.post(f"{PAYMENT_API}/pay", json={"amount": 100})
    assert pr.status_code == 500
    
    httpx.post(f"{FAULT_API}/faults/{fault_id}/cleanup")
    
    pr = httpx.post(f"{PAYMENT_API}/pay", json={"amount": 100})
    assert pr.status_code == 200
