from typing import Dict, Any, List
import logging
from datetime import datetime
from app.schemas.all import VerificationResult, VerificationCheck

logger = logging.getLogger(__name__)

from app.services.remediation import get_simulated_state

def run_deterministic_checks(action_result: Dict[str, Any], state: Dict[str, Any]) -> List[VerificationCheck]:
    checks = []
    action_type = action_result.get("action_type")
    target = action_result.get("target")

    simulated_state = get_simulated_state(target) if target else {}

    if action_type == "RESTART_SERVICE":
        checks.append(VerificationCheck(
            name="service_exists",
            passed=bool(target),
            observed=f"Service {target} exists" if target else "No target",
            expected=f"Service {target} exists"
        ))

        status = simulated_state.get("status", "unknown")
        passed = (status == "healthy")
        checks.append(VerificationCheck(
            name="service_health",
            passed=passed,
            observed=status,
            expected="healthy"
        ))

    elif action_type == "SCALE_SERVICE":
        expected_replicas = action_result.get("new_state", {}).get("replicas", 1)
        actual_replicas = simulated_state.get("replicas", -1)
        checks.append(VerificationCheck(
            name="replica_count",
            passed=(str(actual_replicas) == str(expected_replicas)),
            observed=f"{actual_replicas} replicas running",
            expected=f"{expected_replicas} replicas running"
        ))

        status = simulated_state.get("status", "unknown")
        checks.append(VerificationCheck(
            name="service_health",
            passed=(status == "healthy"),
            observed=status,
            expected="healthy"
        ))

    elif action_type == "ROLLBACK_SERVICE":
        expected_version = action_result.get("new_state", {}).get("version", "unknown")
        actual_version = simulated_state.get("version", "unknown")
        checks.append(VerificationCheck(
            name="service_version",
            passed=(str(actual_version) == str(expected_version)),
            observed=actual_version,
            expected=expected_version
        ))

        status = simulated_state.get("status", "unknown")
        checks.append(VerificationCheck(
            name="service_health",
            passed=(status == "healthy"),
            observed=status,
            expected="healthy"
        ))

    else:
        checks.append(VerificationCheck(
            name="unknown_action_verification",
            passed=False,
            observed=f"Cannot verify unknown action {action_type}",
            expected="Known action"
        ))

    return checks

def perform_verification(action_result: Dict[str, Any], state: Dict[str, Any]) -> VerificationResult:
    # 1. Deterministic checks
    checks = run_deterministic_checks(action_result, state)

    # 2. Extract Evidence
    evidence_list = state.get("evidence", [])
    valid_evidence_ids = [ev.get("evidence_id") for ev in evidence_list if "evidence_id" in ev]

    # The proposal contains evidence_ids that it used.
    # We require at least some valid evidence IDs in the incident to consider it verifiable
    # (Or the verification step itself could generate new evidence).
    # For this exercise, we'll enforce that the state has SOME evidence.
    if not valid_evidence_ids:
        checks.append(VerificationCheck(
            name="evidence_validation",
            passed=False,
            observed="No valid evidence found in state",
            expected="At least one valid evidence ID"
        ))

    # 3. Evaluate overall success
    all_passed = all(check.passed for check in checks)

    # 4. Use an LLM for summarization or final confidence if necessary
    status = "VERIFIED_SUCCESS" if all_passed else "VERIFIED_FAILURE"
    summary = f"Verification {'succeeded' if all_passed else 'failed'} for {action_result.get('action_type')} on {action_result.get('target')}."

    # 5. Construct Result
    return VerificationResult(
        verified=all_passed,
        verification_status=status,
        summary=summary,
        checks=checks,
        evidence_ids=valid_evidence_ids,
        confidence=1.0 if all_passed else 0.5,
        timestamp=datetime.utcnow()
    )
