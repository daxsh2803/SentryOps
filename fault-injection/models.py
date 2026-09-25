
from pydantic import BaseModel
from typing import Optional, Dict, Any
from enum import Enum
import uuid
import datetime

class FaultStatus(str, Enum):
    INACTIVE = 'INACTIVE'
    INJECTING = 'INJECTING'
    ACTIVE = 'ACTIVE'
    STOPPING = 'STOPPING'

class FaultRequest(BaseModel):
    fault_type: str
    target_service: str
    parameters: Optional[Dict[str, Any]] = {}

class FaultModel(BaseModel):
    fault_id: str
    incident_id: str
    fault_type: str
    target_service: str
    status: FaultStatus
    started_at: Optional[datetime.datetime] = None
    ended_at: Optional[datetime.datetime] = None
    parameters: Dict[str, Any]
    ground_truth_root_cause: str
    description: str

