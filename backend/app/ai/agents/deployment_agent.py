from app.ai.state import InvestigationState
from typing import Dict, Any
import httpx
import os
import uuid
from datetime import datetime

FAULT_API_URL = os.getenv("FAULT_API_URL", "http://fault-injection:8005")

def deployment_agent_node(state: InvestigationState) -> Dict[str, Any]:
    new_timeline = ["AGENT_STARTED: DeploymentAgent"]
    findings = []
    new_evidence = []
    new_errors = []
    now_iso = datetime.utcnow().isoformat()
    
    service = state.get("affected_service", "")
    
    # Note explicit availability of real CI/CD deployment tracking
    findings.append({
        "status": "deployment_metadata_unavailable",
        "deployment_metadata_available": False,
        "service": service,
        "message": "No CI/CD pipeline or deployment tracking service configured in environment."
    })
    
    # Query synthetic fault injection service to capture active changes/fault context
    try:
        r = httpx.get(f"{FAULT_API_URL}/faults", timeout=5)
        if r.status_code == 200:
            faults = r.json()
            active_faults = [f for f in faults if f.get("status") == "ACTIVE" and f.get("target_service") == service]
            
            if not active_faults:
                findings.append({
                    "status": "no_synthetic_faults_found",
                    "synthetic_faults_count": 0,
                    "service": service
                })
            else:
                findings.append({
                    "status": "synthetic_faults_found",
                    "synthetic_faults_count": len(active_faults),
                    "service": service
                })
                for fault in active_faults:
                    ev_id = f"EV-CHANGE-{uuid.uuid4().hex[:6].upper()}"
                    fault_ts = fault.get("injected_at") or now_iso
                    new_evidence.append({
                        "evidence_id": ev_id,
                        "evidence_type": "CHANGE",
                        "source": "synthetic-fault-injection",
                        "service": service,
                        "timestamp": fault_ts,
                        "summary": f"Synthetic fault injection active on {service}: {fault.get('fault_type')}",
                        "payload": fault,
                        "confidence": 0.95
                    })
                new_timeline.append("EVIDENCE_COLLECTED: CHANGE")
        else:
            new_errors.append(f"Fault API returned {r.status_code}")
    except Exception as e:
        new_errors.append(f"DeploymentAgent Error: {str(e)}")
        
    new_timeline.append("AGENT_COMPLETED: DeploymentAgent")
    return {
        "deployment_findings": findings,
        "evidence": new_evidence,
        "errors": new_errors,
        "timeline": new_timeline,
    }
