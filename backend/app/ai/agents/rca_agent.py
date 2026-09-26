from app.ai.state import InvestigationState
from app.ai.llm import get_llm
from langchain_core.messages import HumanMessage
from typing import Dict, Any
import json

def rca_agent_node(state: InvestigationState) -> Dict[str, Any]:
    new_timeline = ["AGENT_STARTED: RCAAgent"]
    new_errors = []
    root_cause = "Unknown"
    confidence = 0.0
    evidence_ids = []
    
    llm = get_llm()
    prompt = f"Analyze incident {state.get('incident_id', '')} on {state.get('affected_service', '')}. Evidence: {state.get('evidence', [])}. Return JSON with root_cause, confidence, evidence_ids (list), explanation."
    
    try:
        res = llm.invoke([HumanMessage(content=prompt)])
        content = res.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        parsed = json.loads(content)
        root_cause = parsed.get("root_cause", "Unknown")
        confidence = float(parsed.get("confidence", 0.0))
        
        collected_ids = [e["evidence_id"] for e in state.get("evidence", [])]
        evidence_ids = parsed.get("evidence_ids", []) or collected_ids
        new_timeline.append("RCA_GENERATED")
    except Exception as e:
        new_errors.append(f"RCAAgent Error: {str(e)}")
        root_cause = f"Failed to generate RCA: {str(e)}"
        confidence = 0.0
        evidence_ids = []

    new_timeline.append("AGENT_COMPLETED: RCAAgent")
    return {
        "root_cause": root_cause,
        "root_cause_confidence": confidence,
        "root_cause_evidence_ids": evidence_ids,
        "timeline": new_timeline,
        "errors": new_errors,
    }
