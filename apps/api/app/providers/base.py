from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    @abstractmethod
    def complete_json(self, prompt: str) -> dict:
        """Return structured JSON from an LLM-compatible provider."""
