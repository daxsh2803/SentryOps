
from .base import BaseScenario
from registry import registry

class PaymentCrashScenario(BaseScenario):
    @property
    def ground_truth_root_cause(self) -> str:
        return 'payment-service unavailable'
        
    @property
    def description(self) -> str:
        return 'Simulates a crash of the payment service'
        
    def start(self):
        self.set_fault_state({'crashed': True})
        
    def stop(self):
        self.clear_fault_state()

registry.register('payment_service_crash', PaymentCrashScenario)

