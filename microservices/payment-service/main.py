from fastapi import FastAPI, Request, HTTPException
from obs import setup_observability
from opentelemetry import trace
import redis
import os
import json
import asyncio
import random

app = FastAPI(title='Payment Service')
logger = setup_observability(app, 'payment-service')

redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
r = redis.from_url(redis_url)

@app.get('/health')
def health():
    return {'status': 'ok', 'service': 'payment-service'}

async def check_faults(req_id: str):
    # PaymentCrashScenario
    crash_state = r.get('fault:payment-service:PaymentCrashScenario')
    if crash_state:
        state = json.loads(crash_state)
        if state.get('crashed'):
            logger.error('Payment Service crashed (Fault Injected)', extra={'request_id': req_id})
            raise HTTPException(status_code=503, detail='Service Unavailable')
            
    # HTTP500Scenario
    err_state = r.get('fault:payment-service:HTTP500Scenario')
    if err_state:
        state = json.loads(err_state)
        rate = state.get('error_rate', 0)
        if random.random() < rate:
            logger.error('Injected HTTP 500 Spike', extra={'request_id': req_id})
            raise HTTPException(status_code=500, detail='Internal Server Error')
            
    # LatencyScenario
    lat_state = r.get('fault:payment-service:LatencyScenario')
    if lat_state:
        state = json.loads(lat_state)
        delay_ms = state.get('delay_ms', 0)
        if delay_ms > 0:
            logger.info(f'Injecting {delay_ms}ms latency', extra={'request_id': req_id})
            await asyncio.sleep(delay_ms / 1000.0)

    # DBExhaustionScenario
    db_state = r.get('fault:payment-service:DBExhaustionScenario')
    if db_state:
        state = json.loads(db_state)
        if state.get('db_exhausted'):
            logger.error('Database connection pool exhausted', extra={'request_id': req_id})
            await asyncio.sleep(1) # simulate timeout
            raise HTTPException(status_code=500, detail='DB Connection Error')
            
    # BadConfigurationScenario
    cfg_state = r.get('fault:payment-service:BadConfigurationScenario')
    if cfg_state:
        state = json.loads(cfg_state)
        if state.get('bad_config'):
            logger.error('Bad configuration for downstream service', extra={'request_id': req_id})
            raise HTTPException(status_code=502, detail='Bad Gateway')


@app.post('/pay')
async def process_payment(request: Request):
    data = await request.json()
    req_id = request.headers.get('X-Request-ID', 'unknown')
    logger.info(f"Processing payment for amount {data.get('amount')}", extra={'request_id': req_id})
    
    current_span = trace.get_current_span()
    current_span.set_attribute("request_id", req_id)
    
    # Fault Injection Check
    await check_faults(req_id)
    
    return {'status': 'success', 'amount_paid': data.get('amount'), 'req_id': req_id}
