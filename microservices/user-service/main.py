from fastapi import FastAPI
from obs import setup_observability

app = FastAPI(title='User Service')
logger = setup_observability(app, 'user-service')

@app.get('/health')
def health():
    return {'status': 'ok', 'service': 'user-service'}

@app.get('/users/{user_id}')
def get_user(user_id: int):
    logger.info(f"Fetching user {user_id}")
    return {'user_id': user_id, 'name': 'John Doe'}
