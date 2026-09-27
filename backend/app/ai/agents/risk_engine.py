from typing import Dict, Any
import logging
from app.ai.state import InvestigationState
from app.schemas.all import RemediationProposal, RiskAssessment
from app.services.remediation import evaluate_risk, execute_controlled_action

logger = logging.getLogger(__name__)

def risk_engine_node(state: InvestigationState) -> Dict[str, Any]:
    logger.info("Running Risk Engine")

    proposal_dict = state.get("remediation_proposal")
    if not proposal_dict:
        return {
            "errors": ["No remediation proposal found in state"],
            "timeline": ["RISK_ENGINE_FAILED"]
        }

    try:
        proposal = RemediationProposal(**proposal_dict)
        risk = evaluate_risk(proposal)

        updates = {
            "risk_assessment": risk.model_dump(),
            "timeline": [f"RISK_ASSESSED: {risk.risk_level}"]
        }

        if risk.requires_approval:
            updates["approval_status"] = "PENDING_APPROVAL"
            updates["timeline"].append("APPROVAL_REQUIRED")
        else:
            if risk.allowed:
                updates["approval_status"] = "APPROVED"
                # Automatically execute if allowed and doesn't require approval
                action_result = execute_controlled_action(proposal)
                updates["action_result"] = action_result.model_dump()
                status_str = "SUCCESS" if action_result.success else "FAILED"
                updates["timeline"].append(f"ACTION_EXECUTED: {status_str}")
            else:
                updates["approval_status"] = "REJECTED"
                updates["timeline"].append("ACTION_REJECTED")

        return updates
    except Exception as e:
        logger.error(f"Risk Engine failed: {e}")
        return {
            "errors": [f"Risk Engine error: {str(e)}"],
            "timeline": ["RISK_ENGINE_FAILED"]
        }
