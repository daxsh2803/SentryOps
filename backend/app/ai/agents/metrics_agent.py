from app.ai.state import InvestigationState
from typing import Dict, Any
import httpx
import os
import uuid

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")

def metrics_agent_node(state: InvestigationState) -> Dict[str, Any]:
    new_timeline = ["AGENT_STARTED: MetricsAgent"]
    findings = []
    new_evidence = []
    new_errors = []
    
    service = state.get("affected_service", "")
    # A simple metric check for the service
    query = f'sum(rate(http_requests_total{{app="{service}"}}[5m]))'
    
    try:
        r = httpx.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query}, timeout=5)
        if r.status_code == 200:
            data = r.json()
            results = data.get("data", {}).get("result", [])
            if not results:
                findings.append({"status": "no_metrics_found", "service": service})
            else:
                findings.append({"status": "metrics_found", "data": results})
                ev_id = f"EV-METRIC-{uuid.uuid4().hex[:6].upper()}"
                new_evidence.append({
                    "evidence_id": ev_id,
                    "evidence_type": "METRIC",
                    "source": "prometheus",
                    "service": service,
                    "summary": f"Metrics for {service}",
                    "payload": data,
                    "confidence": 0.8
                })
                new_timeline.append("EVIDENCE_COLLECTED: METRIC")
        else:
            new_errors.append(f"Prometheus returned {r.status_code}")
    except Exception as e:
        new_errors.append(f"MetricsAgent Error: {str(e)}")

    new_timeline.append("AGENT_COMPLETED: MetricsAgent")
    return {
        "metric_findings": findings,
        "evidence": new_evidence,
        "errors": new_errors,
        "timeline": new_timeline,
    }
