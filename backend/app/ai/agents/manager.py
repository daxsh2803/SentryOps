from app.ai.state import InvestigationState
from typing import Dict, Any

def incident_manager_node(state: InvestigationState) -> Dict[str, Any]:
    plan = f"Investigate {state.get('affected_service', '')} around the time of the incident to find {state.get('fault_type', '')} signs."
    return {
        "investigation_plan": plan,
        "timeline": [
            "AGENT_STARTED: IncidentManager",
            "AGENT_COMPLETED: IncidentManager"
        ]
    }
