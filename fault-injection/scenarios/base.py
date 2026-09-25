
from abc import ABC, abstractmethod
import redis
import os
import json

redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
r = redis.from_url(redis_url)

class BaseScenario(ABC):
    def __init__(self, fault_id: str, target_service: str, parameters: dict):
        self.fault_id = fault_id
        self.target_service = target_service
        self.parameters = parameters
        
    @property
    @abstractmethod
    def ground_truth_root_cause(self) -> str:
        pass
        
    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass
        
    def set_fault_state(self, state: dict):
        r.set(f'fault:{self.target_service}:{self.__class__.__name__}', json.dumps(state))
        
    def clear_fault_state(self):
        r.delete(f'fault:{self.target_service}:{self.__class__.__name__}')

