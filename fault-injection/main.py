
from fastapi import FastAPI, HTTPException
from models import FaultRequest, FaultModel
from manager import manager
from registry import registry

app = FastAPI(title='Fault Injection API')

@app.get('/faults')
def list_faults():
    return manager.get_all()

@app.get('/faults/types')
def list_fault_types():
    return registry.get_all()

@app.get('/faults/{fault_id}')
def get_fault(fault_id: str):
    try:
        return manager.get_fault(fault_id)
    except ValueError:
        raise HTTPException(status_code=404, detail='Fault not found')

@app.post('/faults/inject', response_model=FaultModel)
def inject_fault(req: FaultRequest):
    try:
        return manager.inject(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post('/faults/{fault_id}/stop', response_model=FaultModel)
def stop_fault(fault_id: str):
    try:
        return manager.stop(fault_id)
    except ValueError:
        raise HTTPException(status_code=404, detail='Fault not found')

@app.post('/faults/{fault_id}/cleanup')
def cleanup_fault(fault_id: str):
    manager.cleanup(fault_id)
    return {'status': 'cleaned'}

