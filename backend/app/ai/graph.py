from langgraph.graph import StateGraph, START, END
from app.ai.state import InvestigationState
from app.ai.agents.manager import incident_manager_node
from app.ai.agents.log_agent import log_agent_node
from app.ai.agents.metrics_agent import metrics_agent_node
from app.ai.agents.rca_agent import rca_agent_node

def build_investigation_graph():
    builder = StateGraph(InvestigationState)
    
    # Add nodes
    builder.add_node("manager", incident_manager_node)
    builder.add_node("log_agent", log_agent_node)
    builder.add_node("metrics_agent", metrics_agent_node)
    builder.add_node("rca_agent", rca_agent_node)
    
    # Define edges
    builder.add_edge(START, "manager")
    builder.add_edge("manager", "log_agent")
    builder.add_edge("manager", "metrics_agent")
    builder.add_edge("log_agent", "rca_agent")
    builder.add_edge("metrics_agent", "rca_agent")
    builder.add_edge("rca_agent", END)
    
    return builder.compile()

graph = build_investigation_graph()
