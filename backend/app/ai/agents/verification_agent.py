from typing import Dict, Any
import logging
from app.ai.state import InvestigationState
from app.services.verification import perform_verification

logger = logging.getLogger(__name__)

def verification_agent_node(state: InvestigationState) -> Dict[str, Any]:
    logger.info("Running Verification Agent")

    action_result = state.get("action_result")

    # Verification should only happen if there is an action_result, it was successful, and an execution ID is present
    if not action_result or not action_result.get("success"):
        logger.warning("No successful action result to verify. Skipping verification.")
        return {
            "timeline": ["VERIFICATION_SKIPPED: No successful action to verify"]
        }

    execution_id = action_result.get("execution_id")
    if not execution_id:
        logger.warning("Action result missing execution_id. Rejecting fabricated action result.")
        return {
            "timeline": ["VERIFICATION_SKIPPED: Missing execution_id"]
        }

    try:
        # We delegate to the deterministic verification service
        verif_result = perform_verification(action_result, state)

        updates = {
            "verification_result": verif_result.model_dump(),
            "timeline": [f"VERIFICATION_COMPLETED: {'SUCCESS' if verif_result.verified else 'FAILED'}"]
        }

        # Determine next incident status
        if verif_result.verified:
            updates["status"] = "RESOLVED"
            updates["timeline"].append("INCIDENT_RESOLVED")
        else:
            updates["status"] = "INVESTIGATING" # Back to investigation
            updates["timeline"].append("INCIDENT_REINVESTIGATION_REQUIRED")

        return updates
    except Exception as e:
        logger.error(f"Verification Agent failed: {e}")
        return {
            "errors": [f"Verification Agent error: {str(e)}"],
            "timeline": ["VERIFICATION_AGENT_FAILED"]
        }
