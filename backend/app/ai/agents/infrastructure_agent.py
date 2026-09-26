from app.ai.state import InvestigationState
from typing import Dict, Any
import httpx
import os
import uuid
from datetime import datetime

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")

def infrastructure_agent_node(state: InvestigationState) -> Dict[str, Any]:
    new_timeline = ["AGENT_STARTED: InfrastructureAgent"]
    findings = []
    new_evidence = []
    new_errors = []
    now_iso = datetime.utcnow().isoformat()
    
    service = state.get("affected_service", "")
    
    # Query the 'up' metric or generic system resource metric for the service/infrastructure
    # Using 'up' to check if the service endpoints are up according to prometheus
    query = f'up{{job="{service}"}}'
    
    try:
        r = httpx.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query}, timeout=5)
        if r.status_code == 200:
            data = r.json()
            results = data.get("data", {}).get("result", [])
            if not results:
                # If job doesn't match, just fallback to generic check
                query_all = "up"
                r_all = httpx.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query_all}, timeout=5)
                if r_all.status_code == 200:
                    results = r_all.json().get("data", {}).get("result", [])

            findings.append({"status": "infrastructure_checked", "data": results})
            ev_id = f"EV-INFRA-{uuid.uuid4().hex[:6].upper()}"
            new_evidence.append({
                "evidence_id": ev_id,
                "evidence_type": "INFRASTRUCTURE",
                "source": "prometheus",
                "service": service,
                "timestamp": now_iso,
                "summary": f"Infrastructure health for {service}",
                "payload": {"up_metrics": results},
                "confidence": 0.8
            })
            new_timeline.append("EVIDENCE_COLLECTED: INFRASTRUCTURE")
        else:
            new_errors.append(f"Prometheus returned {r.status_code} in Infra check")
    except Exception as e:
        new_errors.append(f"InfrastructureAgent Error: {str(e)}")
        
    new_timeline.append("AGENT_COMPLETED: InfrastructureAgent")
    return {
        "infrastructure_findings": findings,
        "evidence": new_evidence,
        "errors": new_errors,
        "timeline": new_timeline,
    }
