from app.providers.base import BaseLLMProvider


class MockLLMProvider(BaseLLMProvider):
    def complete_json(self, prompt: str) -> dict:
        return {"provider": "mock", "prompt_length": len(prompt)}
