from app.providers.base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    def complete_json(self, prompt: str) -> dict:
        raise NotImplementedError("OpenAIProvider is intentionally stubbed until API-key based runs are enabled.")
