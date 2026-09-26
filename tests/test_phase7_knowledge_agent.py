import pytest
from app.ai.state import InvestigationState
from app.ai.agents.knowledge_agent import knowledge_agent_node

def test_knowledge_agent_no_context():
    # If there is no DB or context, it should gracefully return empty findings
    state: InvestigationState = {
        "incident_id": "INC-123",
        "affected_service": "order-service",
        "incident_context": "Connection timeout",
        "status": "INVESTIGATING",
        "evidence": [],
        "errors": [],
        "timeline": []
    }
    
    # We test that the node doesn't crash when DB is empty or missing pgvector in test env
    try:
        res = knowledge_agent_node(state)
        assert "knowledge_findings" in res
    except Exception as e:
        pytest.fail(f"Knowledge agent raised exception: {e}")
