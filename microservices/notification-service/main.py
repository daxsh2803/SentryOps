
from fastapi import FastAPI, Request
import os
import redis

app = FastAPI(title='Notification Service')
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
    # Save to redis just to use it
    r.set(f'notification:{req_id}', data.get('message', ''))
    return {'status': 'sent', 'req_id': req_id}

