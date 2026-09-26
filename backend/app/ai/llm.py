import os
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage

class MockChatModel(BaseChatModel):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        from langchain_core.outputs import ChatResult, ChatGeneration
        content = "{ \"root_cause\": \"Mocked Root Cause\", \"confidence\": 0.9, \"explanation\": \"Deterministic mock explanation\", \"evidence_ids\": [] }"
        if "investigation plan" in str(messages).lower():
            content = "1. Check logs\n2. Check metrics"
        elif "json" in str(messages).lower():
            pass
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])
    
    def _llm_type(self):
        return "mock"
        
    @property
    def _identifying_params(self):
        return {}

def get_llm():
    if os.getenv("MOCK_LLM", "true").lower() == "true":
        return MockChatModel()
    return ChatOpenAI(temperature=0)
