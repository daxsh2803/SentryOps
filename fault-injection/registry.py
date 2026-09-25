
from typing import Dict, Type
import logging

logger = logging.getLogger(__name__)

class FaultRegistry:
    def __init__(self):
        self._scenarios = {}
        
    def register(self, fault_type: str, scenario_cls: Type):
        self._scenarios[fault_type] = scenario_cls
        
    def get(self, fault_type: str) -> Type:
        if fault_type not in self._scenarios:
            raise ValueError(f'Unknown fault_type: {fault_type}')
        return self._scenarios[fault_type]
        
    def get_all(self):
        return list(self._scenarios.keys())

registry = FaultRegistry()

