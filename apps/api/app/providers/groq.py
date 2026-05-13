import json
import logging
import time

import httpx

from app.config import get_settings
from app.logging_utils import log_event
from app.providers.base import BaseLLMProvider


logger = logging.getLogger(__name__)


class GroqProvider(BaseLLMProvider):
    endpoint = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.groq_model
        self.api_key_configured = bool(settings.groq_api_key)
        log_event(
            logger,
            logging.INFO,
            "llm.groq.initialized",
            model=self.model,
            api_key_configured=self.api_key_configured,
        )

    def complete_json(self, prompt: str) -> dict:
        settings = get_settings()
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is not configured.")

        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.groq_model,
            "messages": [
                {"role": "system", "content": "Return JSON only. Do not include markdown, prose, or code fences."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }

        last_error: Exception | None = None
        for attempt in range(2):
            log_event(logger, logging.INFO, "llm.groq.request.start", model=settings.groq_model, prompt_chars=len(prompt), attempt=attempt + 1)
            try:
                response = httpx.post(self.endpoint, headers=headers, json=payload, timeout=25)
                if response.status_code >= 500:
                    response.raise_for_status()
                if response.status_code == 429:
                    response.raise_for_status()
                response.raise_for_status()
                body = response.json()
                content = body["choices"][0]["message"]["content"]
                if isinstance(content, dict):
                    return content
                return json.loads(content)
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_error = exc
                retryable = isinstance(exc, (httpx.TimeoutException, httpx.TransportError)) or (
                    isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500
                )
                log_event(
                    logger,
                    logging.WARNING,
                    "llm.groq.request.failure",
                    error_type=type(exc).__name__,
                    status_code=getattr(getattr(exc, "response", None), "status_code", None),
                    retryable=retryable and attempt == 0,
                )
                if retryable and attempt == 0:
                    time.sleep(0.25)
                    continue
                raise
            except json.JSONDecodeError as exc:
                log_event(logger, logging.WARNING, "llm.groq.response.parse_failure", error=str(exc))
                raise
        raise RuntimeError(f"Groq request failed: {last_error}")

    def smoke_test(self) -> bool:
        try:
            return bool(self.complete_json('Return exactly this JSON object: {"ok": true}'))
        except Exception as exc:
            log_event(logger, logging.WARNING, "llm.groq.smoke.failure", error_type=type(exc).__name__, error=str(exc))
            return False
