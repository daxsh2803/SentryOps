
from fastapi import FastAPI, Request, HTTPException
import httpx
import os
import uuid

app = FastAPI(title='Order Service')
PAYMENT_SERVICE_URL = os.getenv('PAYMENT_SERVICE_URL', 'http://payment-service:8002')
NOTIFICATION_SERVICE_URL = os.getenv('NOTIFICATION_SERVICE_URL', 'http://notification-service:8003')

@app.get('/health')
def health():
    return {'status': 'ok', 'service': 'order-service'}

@app.post('/orders')
async def process_order(request: Request):
    data = await request.json()
    req_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
    headers = {'X-Request-ID': req_id}
    
    # Simulate payment
    async with httpx.AsyncClient() as client:
        pay_resp = await client.post(f'{PAYMENT_SERVICE_URL}/pay', json={'amount': data.get('amount', 0)}, headers=headers)
        if pay_resp.status_code != 200:
            raise HTTPException(status_code=400, detail='Payment failed')
            
        # Simulate notification
        await client.post(f'{NOTIFICATION_SERVICE_URL}/notify', json={'message': 'Order processed'}, headers=headers)
        
    return {'order_id': str(uuid.uuid4()), 'status': 'completed', 'req_id': req_id}

