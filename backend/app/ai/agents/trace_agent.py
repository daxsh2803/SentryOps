from app.ai.state import InvestigationState
from typing import Dict, Any, List
import httpx
import os
import uuid
from datetime import datetime

JAEGER_URL = os.getenv("JAEGER_URL", "http://jaeger:16686")

def parse_jaeger_traces(data: Dict[str, Any], target_service: str) -> List[Dict[str, Any]]:
    traces_summary = []
    traces = data.get("data", [])
    
    for trace in traces:
        trace_id = trace.get("traceID", "")
        processes = trace.get("processes", {})
        spans = trace.get("spans", [])
        
        parsed_spans = []
        has_error = False
        error_count = 0
        
        for span in spans:
            span_id = span.get("spanID", "")
            operation = span.get("operationName", "")
            duration_us = span.get("duration", 0)
            start_time_us = span.get("startTime", 0)
            
            start_iso = None
            if start_time_us:
                try:
                    start_iso = datetime.utcfromtimestamp(start_time_us / 1_000_000).isoformat()
                except Exception:
                    start_iso = None
                    
            proc_id = span.get("processID", "")
            span_service = processes.get(proc_id, {}).get("serviceName", target_service)
            
            tags = {t.get("key"): t.get("value") for t in span.get("tags", []) if isinstance(t, dict)}
            is_error = bool(tags.get("error", False))
            http_status = tags.get("http.status_code") or tags.get("http.response.status_code")
            
            if is_error or (http_status and str(http_status).startswith("5")):
                has_error = True
                error_count += 1
                
            parent_id = None
            for ref in span.get("references", []):
                if ref.get("refType") == "CHILD_OF":
                    parent_id = ref.get("spanID")
                    break
                    
            parsed_spans.append({
                "span_id": span_id,
                "service": span_service,
                "operation": operation,
                "duration_ms": round(duration_us / 1000.0, 2) if duration_us else 0.0,
                "start_time": start_iso,
                "parent_span_id": parent_id,
                "http_status": http_status,
                "is_error": is_error,
                "error_message": tags.get("error.message") or tags.get("message")
            })
            
        traces_summary.append({
            "trace_id": trace_id,
            "span_count": len(spans),
            "error_span_count": error_count,
            "has_errors": has_error,
            "spans": parsed_spans
        })
        
    return traces_summary

def trace_agent_node(state: InvestigationState) -> Dict[str, Any]:
    new_timeline = ["AGENT_STARTED: TraceAgent"]
    findings = []
    new_evidence = []
    new_errors = []
    now_iso = datetime.utcnow().isoformat()
    
    service = state.get("affected_service", "")
    
    try:
        r = httpx.get(f"{JAEGER_URL}/api/traces", params={"service": service, "limit": 10}, timeout=5)
        if r.status_code == 200:
            data = r.json()
            results = data.get("data", [])
            if not results:
                findings.append({"status": "no_traces_found", "service": service})
            else:
                parsed_traces = parse_jaeger_traces(data, service)
                error_traces = [t for t in parsed_traces if t["has_errors"]]
                findings.append({
                    "status": "traces_found",
                    "total_traces": len(parsed_traces),
                    "error_traces_count": len(error_traces),
                    "service": service,
                    "traces": parsed_traces
                })
                
                # Determine representative timestamp from parsed trace or fallback to current UTC
                evidence_ts = now_iso
                if parsed_traces and parsed_traces[0].get("spans"):
                    for s in parsed_traces[0]["spans"]:
                        if s.get("start_time"):
                            evidence_ts = s["start_time"]
                            break
                            
                ev_id = f"EV-TRACE-{uuid.uuid4().hex[:6].upper()}"
                summary_msg = f"Found {len(parsed_traces)} traces ({len(error_traces)} with errors) for {service}"
                new_evidence.append({
                    "evidence_id": ev_id,
                    "evidence_type": "TRACE",
                    "source": "jaeger",
                    "service": service,
                    "timestamp": evidence_ts,
                    "summary": summary_msg,
                    "payload": {
                        "traces": parsed_traces,
                        "raw_trace_count": len(results)
                    },
                    "confidence": 0.85 if error_traces else 0.70
                })
                new_timeline.append("EVIDENCE_COLLECTED: TRACE")
        else:
            new_errors.append(f"Jaeger returned {r.status_code}")
    except Exception as e:
        new_errors.append(f"TraceAgent Error: {str(e)}")
        
    new_timeline.append("AGENT_COMPLETED: TraceAgent")
    return {
        "trace_findings": findings,
        "evidence": new_evidence,
        "errors": new_errors,
        "timeline": new_timeline,
    }
