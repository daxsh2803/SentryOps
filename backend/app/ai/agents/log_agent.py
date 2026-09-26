from app.ai.state import InvestigationState
from typing import Dict, Any
import httpx
import os
import uuid

LOKI_URL = os.getenv("LOKI_URL", "http://loki:3100")

def log_agent_node(state: InvestigationState) -> Dict[str, Any]:
    new_timeline = ["AGENT_STARTED: LogAgent"]
    findings = []
    new_evidence = []
    new_errors = []
    
    service = state.get("affected_service", "")
    query = f'{{application="{service}"}}'
    
    try:
        r = httpx.get(f"{LOKI_URL}/loki/api/v1/query", params={"query": query}, timeout=5)
        if r.status_code == 200:
            data = r.json()
            results = data.get("data", {}).get("result", [])
            if not results:
                findings.append({"status": "no_logs_found", "service": service})
            else:
                findings.append({"status": "logs_found", "count": len(results)})
                ev_id = f"EV-LOG-{uuid.uuid4().hex[:6].upper()}"
                new_evidence.append({
                    "evidence_id": ev_id,
                    "evidence_type": "LOG",
                    "source": "loki",
                    "service": service,
                    "summary": f"Found logs for {service}",
                    "payload": data,
                    "confidence": 0.8
                })
                new_timeline.append("EVIDENCE_COLLECTED: LOG")
        else:
            new_errors.append(f"Loki returned {r.status_code}")
    except Exception as e:
        new_errors.append(f"LogAgent Error: {str(e)}")
        
    new_timeline.append("AGENT_COMPLETED: LogAgent")
    return {
        "log_findings": findings,
        "evidence": new_evidence,
        "errors": new_errors,
        "timeline": new_timeline,
    }
