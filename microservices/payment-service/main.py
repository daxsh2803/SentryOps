
from fastapi import FastAPI, Request

app = FastAPI(title='Payment Service')

@app.get('/health')
def health():
    return {'status': 'ok', 'service': 'payment-service'}

@app.post('/pay')
async def process_payment(request: Request):
    data = await request.json()
    req_id = request.headers.get('X-Request-ID', 'unknown')
    return {'status': 'success', 'amount_paid': data.get('amount'), 'req_id': req_id}

