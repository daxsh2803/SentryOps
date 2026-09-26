import httpx

def test_api_gateway_health():
    r = httpx.get('http://127.0.0.1:8000/health')
    assert r.status_code == 200
    assert r.json()['status'] == 'ok'

def test_order_service_health():
    r = httpx.get('http://127.0.0.1:8001/health')
    assert r.status_code == 200

def test_payment_service_health():
    r = httpx.get('http://127.0.0.1:8002/health')
    assert r.status_code == 200

def test_notification_service_health():
    r = httpx.get('http://127.0.0.1:8003/health')
    assert r.status_code == 200
    assert r.json()['redis'] == 'ok'

def test_user_service_health():
    r = httpx.get('http://127.0.0.1:8004/health')
    assert r.status_code == 200

def test_order_flow():
    r = httpx.post('http://127.0.0.1:8000/orders', json={'amount': 100})
    assert r.status_code == 200
    data = r.json()
    assert data['status'] == 'completed'
    assert 'order_id' in data

def test_metrics_endpoints():
    for port in [8000, 8001, 8002, 8003, 8004]:
        r = httpx.get(f'http://127.0.0.1:{port}/metrics')
        assert r.status_code == 200
        assert 'http_requests_total' in r.text
