from fastapi import FastAPI, Request
import os
import redis
from obs import setup_observability
from opentelemetry import trace

app = FastAPI(title='Notification Service')
logger = setup_observability(app, 'notification-service')

redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
r = redis.from_url(redis_url)

@app.get('/health')
def health():
    try:
        r.ping()
        redis_status = 'ok'
    except Exception:
        redis_status = 'failed'
    return {'status': 'ok', 'service': 'notification-service', 'redis': redis_status}

@app.post('/notify')
async def notify(request: Request):
    data = await request.json()
    req_id = request.headers.get('X-Request-ID', 'unknown')
    logger.info("Sending notification", extra={'request_id': req_id})
    
    current_span = trace.get_current_span()
    current_span.set_attribute("request_id", req_id)
    
    try:
        r.set(f'notification:{req_id}', data.get('message', ''))
    except Exception as e:
        logger.error(f"Redis error: {e}", extra={'request_id': req_id})
        
    return {'status': 'sent', 'req_id': req_id}
