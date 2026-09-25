
from .base import BaseScenario
from registry import registry

class HTTP500Scenario(BaseScenario):
    @property
    def ground_truth_root_cause(self) -> str:
        return 'injected HTTP 500 failure rate'
        
    @property
    def description(self) -> str:
        return 'Injects HTTP 500 errors at a configurable rate'
        
    def start(self):
        rate = float(self.parameters.get('error_rate', 0.5))
        self.set_fault_state({'error_rate': rate})
        
    def stop(self):
        self.clear_fault_state()

registry.register('http_500_spike', HTTP500Scenario)

