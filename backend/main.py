from fastapi import FastAPI
from app.db.session import engine, Base
from app.api import incidents

# Create all tables for Phase 4 setup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="SentryOps Backend - Incident Management", version="0.4.0")

app.include_router(incidents.router)

@app.get("/health")
def read_root():
    return {"status": "ok", "service": "backend"}
