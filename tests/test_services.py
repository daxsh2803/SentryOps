import httpx
import pytest

def test_api_gateway_health():
    r = httpx.get('http://localhost:8000/health')
    assert r.status_code == 200
    assert r.json()['status'] == 'ok'

def test_order_service_health():
    r = httpx.get('http://localhost:8001/health')
    assert r.status_code == 200

def test_payment_service_health():
    r = httpx.get('http://localhost:8002/health')
    assert r.status_code == 200

def test_notification_service_health():
    r = httpx.get('http://localhost:8003/health')
    assert r.status_code == 200
    assert r.json()['redis'] == 'ok'

def test_user_service_health():
    r = httpx.get('http://localhost:8004/health')
    assert r.status_code == 200

def test_order_flow():
    r = httpx.post('http://localhost:8000/orders', json={'amount': 100})
    assert r.status_code == 200
    data = r.json()
    assert data['status'] == 'completed'
    assert 'order_id' in data

