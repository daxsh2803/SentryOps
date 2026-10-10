import os
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage

class MockChatModel(BaseChatModel):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        import re
        import json
        from langchain_core.outputs import ChatResult, ChatGeneration
        # Extract text content from message objects
        text = " ".join([m.content if hasattr(m, "content") else str(m) for m in messages])
        text_lower = text.lower()

        if "investigation plan" in text_lower:
            content = "1. Check logs\n2. Check metrics"
        elif "remediation agent" in text_lower or ("action_type" in text_lower and "allowlist" in text_lower):
            # Deterministic demonstration fixture under MOCK_LLM=true mode.
            # Clearly labeled to distinguish from live LLM reasoning.
            target_service = "payment-service"
            match_svc = re.search(r"Affected Service:\s*([a-zA-Z0-9_\-]+)", text)
            if match_svc and match_svc.group(1).strip():
                target_service = match_svc.group(1).strip()

            evidence_ids = []
            match_ev = re.search(r"Available Evidence IDs:\s*(\[[^\]]*\])", text)
            if match_ev:
                try:
                    import ast
                    parsed_ev = ast.literal_eval(match_ev.group(1).strip())
                    if isinstance(parsed_ev, list):
                        evidence_ids = [str(eid) for eid in parsed_ev if str(eid).strip()]
                except Exception:
                    pass

            if "service_crash" in text_lower or "crash" in text_lower:
                proposal_data = {
                    "action_type": "RESTART_SERVICE",
                    "target_service": target_service,
                    "parameters": {"instances": "multiple"},
                    "reason": "[DEMO FIXTURE - MOCK_LLM] Deterministic proposal for demonstration: Restart multiple service instances to recover from crash.",
                    "evidence_ids": evidence_ids,
                    "confidence": 0.9
                }
            else:
                proposal_data = {
                    "action_type": "SCALE_SERVICE",
                    "target_service": target_service,
                    "parameters": {"replicas": 2},
                    "reason": "[DEMO FIXTURE - MOCK_LLM] Deterministic proposal for demonstration: Scale service replicas to 2 to alleviate traffic/latency load.",
                    "evidence_ids": evidence_ids,
                    "confidence": 0.9
                }
            content = json.dumps(proposal_data)
        else:
            content = "{ \"root_cause\": \"Mocked Root Cause\", \"confidence\": 0.9, \"explanation\": \"Deterministic mock explanation\", \"evidence_ids\": [] }"

        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])
    
    def _llm_type(self):
        return "mock"
        
    @property
    def _identifying_params(self):
        return {}

def get_llm():
    if os.getenv("MOCK_LLM", "true").lower() == "true":
        return MockChatModel()
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(temperature=0)
