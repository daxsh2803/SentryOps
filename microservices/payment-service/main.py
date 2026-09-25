from fastapi import FastAPI, Request
from obs import setup_observability
from opentelemetry import trace

app = FastAPI(title='Payment Service')
logger = setup_observability(app, 'payment-service')

@app.get('/health')
def health():
    return {'status': 'ok', 'service': 'payment-service'}

@app.post('/pay')
async def process_payment(request: Request):
    data = await request.json()
    req_id = request.headers.get('X-Request-ID', 'unknown')
    logger.info(f"Processing payment for amount {data.get('amount')}", extra={'request_id': req_id})
    
    current_span = trace.get_current_span()
    current_span.set_attribute("request_id", req_id)
    
    return {'status': 'success', 'amount_paid': data.get('amount'), 'req_id': req_id}
