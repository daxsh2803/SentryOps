from typing import Dict, Any, List
import logging
from datetime import datetime
from app.schemas.all import RemediationProposal, RiskAssessment, ActionResult

logger = logging.getLogger(__name__)

SUPPORTED_ACTIONS = {
    "RESTART_SERVICE",
    "SCALE_SERVICE",
    "ROLLBACK_SERVICE"
}

# Simulated infrastructure state for independent verification
SIMULATED_INFRA_STATE = {}

def get_simulated_state(service: str) -> Dict[str, Any]:
    if service not in SIMULATED_INFRA_STATE:
        SIMULATED_INFRA_STATE[service] = {"status": "unhealthy", "replicas": 1, "version": "current"}
    return SIMULATED_INFRA_STATE[service]

def update_simulated_state(service: str, updates: Dict[str, Any]):
    state = get_simulated_state(service)
    state.update(updates)

def evaluate_risk(proposal: RemediationProposal) -> RiskAssessment:
    if proposal.action_type not in SUPPORTED_ACTIONS:
        return RiskAssessment(
            risk_level="HIGH",
            allowed=False,
            requires_approval=True,
            reasons=[f"Unsupported action type: {proposal.action_type}"]
        )

    # Deterministic policy rules
    if proposal.action_type == "ROLLBACK_SERVICE":
        return RiskAssessment(
            risk_level="HIGH",
            allowed=False,
            requires_approval=True,
            reasons=["ROLLBACK_SERVICE always requires human approval"]
        )

    if proposal.action_type == "SCALE_SERVICE":
        target_replicas = proposal.parameters.get("replicas", 1)
        if not isinstance(target_replicas, int) or target_replicas > 5 or target_replicas < 1:
            return RiskAssessment(
                risk_level="HIGH",
                allowed=False,
                requires_approval=True,
                reasons=[f"Invalid or excessive replica count: {target_replicas}"]
            )
        return RiskAssessment(
            risk_level="MEDIUM",
            allowed=True,
            requires_approval=True,
            reasons=["SCALE_SERVICE requires strict validation and approval"]
        )

    if proposal.action_type == "RESTART_SERVICE":
        instances = proposal.parameters.get("instances", "one")
        if instances == "all" or instances == "multiple":
            return RiskAssessment(
                risk_level="MEDIUM",
                allowed=True,
                requires_approval=True,
                reasons=["Restarting multiple instances requires approval"]
            )
        else:
            return RiskAssessment(
                risk_level="LOW",
                allowed=True,
                requires_approval=False,
                reasons=["Restarting a single unhealthy instance is considered safe"]
            )

    return RiskAssessment(
        risk_level="HIGH",
        allowed=False,
        requires_approval=True,
        reasons=["Unknown conditions triggered high risk"]
    )

def execute_controlled_action(proposal: RemediationProposal) -> ActionResult:
    if proposal.action_type not in SUPPORTED_ACTIONS:
        return ActionResult(
            success=False,
            action_type=proposal.action_type,
            target=proposal.target_service,
            message=f"Action rejected: {proposal.action_type} is not supported",
            timestamp=datetime.utcnow()
        )

    try:
        if proposal.action_type == "RESTART_SERVICE":
            return restart_service(proposal)
        elif proposal.action_type == "SCALE_SERVICE":
            return scale_service(proposal)
        elif proposal.action_type == "ROLLBACK_SERVICE":
            return rollback_service(proposal)
    except Exception as e:
        logger.error(f"Action execution failed: {e}")
        return ActionResult(
            success=False,
            action_type=proposal.action_type,
            target=proposal.target_service,
            message=f"Execution error: {str(e)}",
            timestamp=datetime.utcnow()
        )

    return ActionResult(
        success=False,
        action_type=proposal.action_type,
        target=proposal.target_service,
        message="Execution fell through",
        timestamp=datetime.utcnow()
    )

import uuid

def restart_service(proposal: RemediationProposal) -> ActionResult:
    service = proposal.target_service
    if not service:
        raise ValueError("Service name is required")

    update_simulated_state(service, {"status": "healthy"})

    return ActionResult(
        success=True,
        execution_id=f"exec-{uuid.uuid4()}",
        action_type="RESTART_SERVICE",
        target=service,
        previous_state={"status": "unhealthy"},
        new_state={"status": "healthy"},
        message=f"Successfully restarted service {service}",
        timestamp=datetime.utcnow()
    )

def scale_service(proposal: RemediationProposal) -> ActionResult:
    service = proposal.target_service
    if not service:
        raise ValueError("Service name is required")

    replicas = proposal.parameters.get("replicas")
    if replicas is None:
        raise ValueError("Replicas parameter is required for SCALE_SERVICE")

    update_simulated_state(service, {"replicas": replicas, "status": "healthy"})

    return ActionResult(
        success=True,
        execution_id=f"exec-{uuid.uuid4()}",
        action_type="SCALE_SERVICE",
        target=service,
        previous_state={"replicas": 1},
        new_state={"replicas": replicas},
        message=f"Successfully scaled service {service} to {replicas} replicas",
        timestamp=datetime.utcnow()
    )

def rollback_service(proposal: RemediationProposal) -> ActionResult:
    service = proposal.target_service
    if not service:
        raise ValueError("Service name is required")

    version = proposal.parameters.get("version", "previous")

    update_simulated_state(service, {"version": version, "status": "healthy"})

    return ActionResult(
        success=True,
        execution_id=f"exec-{uuid.uuid4()}",
        action_type="ROLLBACK_SERVICE",
        target=service,
        previous_state={"version": "current"},
        new_state={"version": version},
        message=f"Successfully rolled back service {service} to version {version}",
        timestamp=datetime.utcnow()
    )
