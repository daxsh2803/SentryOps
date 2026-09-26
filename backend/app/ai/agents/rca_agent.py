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
    prompt = (
        f"Analyze incident {state.get('incident_id', '')} on {state.get('affected_service', '')}.\n"
        f"Evidence: {state.get('evidence', [])}\n"
        f"Trace Findings: {state.get('trace_findings', [])}\n"
        f"Deployment Findings: {state.get('deployment_findings', [])}\n"
        f"Infrastructure Findings: {state.get('infrastructure_findings', [])}\n"
        f"Knowledge Findings (Historical Runbooks/Context): {state.get('knowledge_findings', [])}\n"
        f"IMPORTANT: Historical knowledge must NOT be treated as ground truth for this incident. Use it only as context/reference.\n"
        f"Return JSON with root_cause, confidence, evidence_ids (list), explanation."
    )
    
    collected_ids = {
        e["evidence_id"]
        for e in state.get("evidence", [])
        if e.get("evidence_id")
    }
    
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
        
        raw_ids = parsed.get("evidence_ids", [])
        if isinstance(raw_ids, list):
            valid_ids = [eid for eid in raw_ids if eid in collected_ids]
        else:
            valid_ids = []
            
        evidence_ids = valid_ids if valid_ids else list(collected_ids)
        new_timeline.append("RCA_GENERATED")
    except Exception as e:
        new_errors.append(f"RCAAgent Error: {str(e)}")
        root_cause = f"Failed to generate RCA: {str(e)}"
        confidence = 0.0
        evidence_ids = list(collected_ids)

    new_timeline.append("AGENT_COMPLETED: RCAAgent")
    return {
        "root_cause": root_cause,
        "root_cause_confidence": confidence,
        "root_cause_evidence_ids": evidence_ids,
        "timeline": new_timeline,
        "errors": new_errors,
    }
