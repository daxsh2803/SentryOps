from fastapi import FastAPI, Request, HTTPException
import httpx
import os
import uuid
from obs import setup_observability
from opentelemetry import trace

app = FastAPI(title='Order Service')
logger = setup_observability(app, 'order-service')

PAYMENT_SERVICE_URL = os.getenv('PAYMENT_SERVICE_URL', 'http://payment-service:8002')
NOTIFICATION_SERVICE_URL = os.getenv('NOTIFICATION_SERVICE_URL', 'http://notification-service:8003')

@app.get('/health')
def health():
    return {'status': 'ok', 'service': 'order-service'}

@app.post('/orders')
async def process_order(request: Request):
    data = await request.json()
    req_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
    logger.info("Processing order", extra={'request_id': req_id})
    headers = {'X-Request-ID': req_id}
    
    current_span = trace.get_current_span()
    current_span.set_attribute("request_id", req_id)
    
    async with httpx.AsyncClient() as client:
        logger.info("Calling payment service", extra={'request_id': req_id})
        pay_resp = await client.post(f'{PAYMENT_SERVICE_URL}/pay', json={'amount': data.get('amount', 0)}, headers=headers)
        if pay_resp.status_code != 200:
            logger.error("Payment failed", extra={'request_id': req_id})
            raise HTTPException(status_code=400, detail='Payment failed')
            
        logger.info("Calling notification service", extra={'request_id': req_id})
        await client.post(f'{NOTIFICATION_SERVICE_URL}/notify', json={'message': 'Order processed'}, headers=headers)
        
    logger.info("Order complete", extra={'request_id': req_id})
    return {'order_id': str(uuid.uuid4()), 'status': 'completed', 'req_id': req_id}
