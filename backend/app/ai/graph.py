from langgraph.graph import StateGraph, START, END
from app.ai.state import InvestigationState
from app.ai.agents.manager import incident_manager_node
from app.ai.agents.log_agent import log_agent_node
from app.ai.agents.metrics_agent import metrics_agent_node
from app.ai.agents.trace_agent import trace_agent_node
from app.ai.agents.deployment_agent import deployment_agent_node
from app.ai.agents.infrastructure_agent import infrastructure_agent_node
from app.ai.agents.knowledge_agent import knowledge_agent_node
from app.ai.agents.rca_agent import rca_agent_node
from app.ai.agents.remediation_agent import remediation_agent_node
from app.ai.agents.risk_engine import risk_engine_node

from app.ai.agents.verification_agent import verification_agent_node

def build_investigation_graph():
    builder = StateGraph(InvestigationState)

    # Add nodes
    builder.add_node("manager", incident_manager_node)
    builder.add_node("log_agent", log_agent_node)
    builder.add_node("metrics_agent", metrics_agent_node)
    builder.add_node("trace_agent", trace_agent_node)
    builder.add_node("deployment_agent", deployment_agent_node)
    builder.add_node("infrastructure_agent", infrastructure_agent_node)
    builder.add_node("knowledge_agent", knowledge_agent_node)
    builder.add_node("rca_agent", rca_agent_node)
    builder.add_node("remediation_agent", remediation_agent_node)
    builder.add_node("risk_engine", risk_engine_node)
    builder.add_node("verification_agent", verification_agent_node)

    # Define edges
    builder.add_edge(START, "manager")
    builder.add_edge("manager", "log_agent")
    builder.add_edge("manager", "metrics_agent")
    builder.add_edge("manager", "trace_agent")
    builder.add_edge("manager", "deployment_agent")
    builder.add_edge("manager", "infrastructure_agent")
    builder.add_edge("manager", "knowledge_agent")

    builder.add_edge("log_agent", "rca_agent")
    builder.add_edge("metrics_agent", "rca_agent")
    builder.add_edge("trace_agent", "rca_agent")
    builder.add_edge("deployment_agent", "rca_agent")
    builder.add_edge("infrastructure_agent", "rca_agent")
    builder.add_edge("knowledge_agent", "rca_agent")

    builder.add_edge("rca_agent", "remediation_agent")
    builder.add_edge("remediation_agent", "risk_engine")

    def route_after_risk_engine(state: InvestigationState) -> str:
        if state.get("approval_status") == "PENDING_APPROVAL":
            return END
        action_result = state.get("action_result")
        if action_result and action_result.get("success"):
            return "verification_agent"
        return END

    builder.add_conditional_edges(
        "risk_engine",
        route_after_risk_engine,
        {
            "verification_agent": "verification_agent",
            END: END
        }
    )

    builder.add_edge("verification_agent", END)

    return builder.compile()

graph = build_investigation_graph()
