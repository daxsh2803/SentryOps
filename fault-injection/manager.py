
import uuid
import datetime
from typing import Dict
from models import FaultModel, FaultStatus, FaultRequest
from registry import registry
import scenarios

class FaultManager:
    def __init__(self):
        self.active_faults: Dict[str, FaultModel] = {}
        self.scenario_instances = {}
        
    def inject(self, req: FaultRequest) -> FaultModel:
        scenario_cls = registry.get(req.fault_type)
        fault_id = f'FAULT-{uuid.uuid4().hex[:8].upper()}'
        incident_id = f'INC-{uuid.uuid4().hex[:6].upper()}'
        
        scenario = scenario_cls(fault_id, req.target_service, req.parameters or {})
        
        fault = FaultModel(
            fault_id=fault_id,
            incident_id=incident_id,
            fault_type=req.fault_type,
            target_service=req.target_service,
            status=FaultStatus.ACTIVE,
            started_at=datetime.datetime.utcnow(),
            parameters=req.parameters or {},
            ground_truth_root_cause=scenario.ground_truth_root_cause,
            description=scenario.description
        )
        
        scenario.start()
        self.active_faults[fault_id] = fault
        self.scenario_instances[fault_id] = scenario
        return fault
        
    def stop(self, fault_id: str) -> FaultModel:
        if fault_id not in self.active_faults:
            raise ValueError('Fault not found')
            
        fault = self.active_faults[fault_id]
        scenario = self.scenario_instances[fault_id]
        
        fault.status = FaultStatus.STOPPING
        scenario.stop()
        
        fault.status = FaultStatus.INACTIVE
        fault.ended_at = datetime.datetime.utcnow()
        return fault
        
    def cleanup(self, fault_id: str):
        if fault_id in self.active_faults:
            if self.active_faults[fault_id].status == FaultStatus.ACTIVE:
                self.stop(fault_id)
            del self.active_faults[fault_id]
            del self.scenario_instances[fault_id]
            
    def get_fault(self, fault_id: str) -> FaultModel:
        if fault_id not in self.active_faults:
            raise ValueError('Fault not found')
        return self.active_faults[fault_id]
        
    def get_all(self):
        return list(self.active_faults.values())

manager = FaultManager()

