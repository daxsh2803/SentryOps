from fastapi import FastAPI

app = FastAPI(title="SentryOps Backend", version="0.1.0")

@app.get("/")
def read_root():
    return {"message": "SentryOps API Foundation (Phase 0)"}
