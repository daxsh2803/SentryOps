
from .base import BaseScenario
from registry import registry

class DBExhaustionScenario(BaseScenario):
    @property
    def ground_truth_root_cause(self) -> str:
        return 'database connection pool exhaustion'
        
    @property
    def description(self) -> str:
        return 'Simulates exhaustion of database connection pool'
        
    def start(self):
        self.set_fault_state({'db_exhausted': True})
        
    def stop(self):
        self.clear_fault_state()

registry.register('db_connection_exhaustion', DBExhaustionScenario)

