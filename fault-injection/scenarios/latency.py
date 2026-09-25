
from .base import BaseScenario
from registry import registry

class LatencyScenario(BaseScenario):
    @property
    def ground_truth_root_cause(self) -> str:
        return 'injected application latency'
        
    @property
    def description(self) -> str:
        return 'Introduces artificial latency into requests'
        
    def start(self):
        delay = int(self.parameters.get('delay_ms', 1000))
        self.set_fault_state({'delay_ms': delay})
        
    def stop(self):
        self.clear_fault_state()

registry.register('artificial_latency', LatencyScenario)

