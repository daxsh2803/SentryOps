from fastapi import FastAPI
from app.db.session import engine, Base, init_db
from app.api import incidents, knowledge

# Initialize extensions
init_db()

# Create all tables for Phase 4 setup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="SentryOps Backend - Incident Management", version="0.4.0")

app.include_router(incidents.router)
app.include_router(knowledge.router)

@app.get("/health")
def read_root():
    return {"status": "ok", "service": "backend"}
