
from fastapi import FastAPI, Request, HTTPException
import httpx
import os
import uuid

app = FastAPI(title='API Gateway')
ORDER_SERVICE_URL = os.getenv('ORDER_SERVICE_URL', 'http://order-service:8001')

@app.get('/health')
def health():
    return {'status': 'ok', 'service': 'api-gateway'}

@app.post('/orders')
async def create_order(request: Request):
    req_id = str(uuid.uuid4())
    data = await request.json()
    headers = {'X-Request-ID': req_id}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f'{ORDER_SERVICE_URL}/orders', json=data, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=str(e))

