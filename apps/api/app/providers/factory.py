import logging

from app.config import get_settings
from app.logging_utils import log_event
from app.providers.base import BaseLLMProvider
from app.providers.groq import GroqProvider
from app.providers.mock import MockLLMProvider
from app.providers.openai import OpenAIProvider
from app.providers.openrouter import OpenRouterProvider


logger = logging.getLogger(__name__)


def get_llm_provider() -> BaseLLMProvider:
    settings = get_settings()
    provider = settings.llm_provider.strip().lower()
    log_event(logger, logging.INFO, "llm.provider.selected", provider=provider or "mock")
    if provider == "groq":
        return GroqProvider()
    if provider == "openrouter":
        return OpenRouterProvider()
    if provider == "openai":
        return OpenAIProvider()
    return MockLLMProvider()
