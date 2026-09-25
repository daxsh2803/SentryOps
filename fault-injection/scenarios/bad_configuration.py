
from .base import BaseScenario
from registry import registry

class BadConfigurationScenario(BaseScenario):
    @property
    def ground_truth_root_cause(self) -> str:
        return 'invalid service configuration'
        
    @property
    def description(self) -> str:
        return 'Simulates bad configuration leading to downstream failures'
        
    def start(self):
        self.set_fault_state({'bad_config': True})
        
    def stop(self):
        self.clear_fault_state()

registry.register('bad_configuration', BadConfigurationScenario)

