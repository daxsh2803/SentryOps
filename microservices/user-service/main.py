
from fastapi import FastAPI

app = FastAPI(title='User Service')

@app.get('/health')
def health():
    return {'status': 'ok', 'service': 'user-service'}

@app.get('/users/{user_id}')
def get_user(user_id: int):
    return {'user_id': user_id, 'name': 'John Doe'}

