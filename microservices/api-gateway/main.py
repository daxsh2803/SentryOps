from fastapi import FastAPI, Request, HTTPException
import httpx
import os
import uuid
from obs import setup_observability
from opentelemetry import trace

app = FastAPI(title='API Gateway')
logger = setup_observability(app, 'api-gateway')

ORDER_SERVICE_URL = os.getenv('ORDER_SERVICE_URL', 'http://order-service:8001')

@app.get('/health')
def health():
    return {'status': 'ok', 'service': 'api-gateway'}

@app.post('/orders')
async def create_order(request: Request):
    req_id = str(uuid.uuid4())
    logger.info(f"Received order request", extra={'request_id': req_id})
    data = await request.json()
    headers = {'X-Request-ID': req_id}
    
    current_span = trace.get_current_span()
    current_span.set_attribute("request_id", req_id)
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f'{ORDER_SERVICE_URL}/orders', json=data, headers=headers)
            resp.raise_for_status()
            logger.info("Order processed successfully", extra={'request_id': req_id})
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Error processing order: {e}", extra={'request_id': req_id})
            raise HTTPException(status_code=500, detail=str(e))
