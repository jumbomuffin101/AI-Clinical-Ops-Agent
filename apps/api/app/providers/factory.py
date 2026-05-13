from app.config import get_settings
from app.providers.base import BaseLLMProvider
from app.providers.mock import MockLLMProvider
from app.providers.openai import OpenAIProvider
from app.providers.openrouter import OpenRouterProvider


def get_llm_provider() -> BaseLLMProvider:
    provider = get_settings().llm_provider.lower()
    if provider == "openrouter":
        return OpenRouterProvider()
    if provider == "openai":
        return OpenAIProvider()
    return MockLLMProvider()
