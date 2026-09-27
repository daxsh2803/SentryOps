from typing import Dict, Any, List
import logging
import json
from langchain_core.messages import HumanMessage
from app.ai.state import InvestigationState
from app.schemas.all import RemediationProposal
from app.ai.llm import get_llm

logger = logging.getLogger(__name__)

def get_remediation_agent():
    return get_llm()

def remediation_agent_node(state: InvestigationState) -> Dict[str, Any]:
    logger.info("Running Remediation Agent")

    agent = get_remediation_agent()

    # Extract available evidence IDs
    available_evidence_ids = [ev.get("evidence_id") for ev in state.get("evidence", []) if "evidence_id" in ev]

    prompt = f"""You are the SentryOps Remediation Agent. Your job is to analyze the investigation state and propose a structured remediation action.

    You must ONLY propose actions from the following allowlist:
    - RESTART_SERVICE
    - SCALE_SERVICE
    - ROLLBACK_SERVICE

    Do NOT propose any arbitrary commands, shell scripts, or unspecified actions.
    Your output must be JSON exactly matching this structure:
    {{
      "action_type": "string (must be from allowlist)",
      "target_service": "string",
      "parameters": {{"key": "value"}},
      "reason": "string",
      "evidence_ids": ["string"],
      "confidence": float
    }}

    Investigation State:
    Incident: {state.get('incident_id', '')}
    Affected Service: {state.get('affected_service', '')}
    Fault Type: {state.get('fault_type', '')}
    Root Cause: {state.get('root_cause', '')}
    Root Cause Confidence: {state.get('root_cause_confidence', 0.0)}
    Root Cause Evidence IDs: {state.get('root_cause_evidence_ids', [])}
    Available Evidence IDs: {available_evidence_ids}
    """

    try:
        res = agent.invoke([HumanMessage(content=prompt)])
        content = res.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        parsed = json.loads(content)

        proposal = RemediationProposal(
            action_type=parsed.get("action_type", ""),
            target_service=parsed.get("target_service", ""),
            parameters=parsed.get("parameters", {}),
            reason=parsed.get("reason", ""),
            evidence_ids=parsed.get("evidence_ids", []),
            confidence=float(parsed.get("confidence", 0.0))
        )

        # Validate evidence IDs
        valid_evidence_ids = [eid for eid in proposal.evidence_ids if eid in available_evidence_ids]
        if set(valid_evidence_ids) != set(proposal.evidence_ids):
            logger.warning("Agent proposed unknown evidence IDs, filtering them out.")
            proposal.evidence_ids = valid_evidence_ids

        return {
            "remediation_proposal": proposal.model_dump(),
            "timeline": ["REMEDIATION_PROPOSED: " + proposal.action_type]
        }
    except Exception as e:
        logger.error(f"Remediation Agent failed: {e}")
        return {
            "errors": [f"Remediation Agent error: {str(e)}"],
            "timeline": ["REMEDIATION_AGENT_FAILED"]
        }
