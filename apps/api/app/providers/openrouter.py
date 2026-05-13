import json
import logging

import httpx

from app.config import get_settings
from app.logging_utils import log_event
from app.providers.base import BaseLLMProvider


logger = logging.getLogger(__name__)


class OpenRouterProvider(BaseLLMProvider):
    endpoint = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.openrouter_model
        self.api_key_configured = bool(settings.openrouter_api_key)
        log_event(
            logger,
            logging.INFO,
            "llm.openrouter.initialized",
            model=self.model,
            api_key_configured=self.api_key_configured,
            site_url_configured=bool(settings.openrouter_site_url),
            app_name_configured=bool(settings.openrouter_app_name),
        )

    def complete_json(self, prompt: str) -> dict:
        settings = get_settings()
        if not settings.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not configured.")

        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        if settings.openrouter_site_url:
            headers["HTTP-Referer"] = settings.openrouter_site_url
        if settings.openrouter_app_name:
            headers["X-Title"] = settings.openrouter_app_name

        payload = {
            "model": settings.openrouter_model,
            "messages": [
                {
                    "role": "system",
                    "content": "Return JSON only. Do not include markdown, prose, or code fences.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        log_event(logger, logging.INFO, "llm.openrouter.request.start", model=settings.openrouter_model, prompt_chars=len(prompt))
        try:
            response = httpx.post(self.endpoint, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            log_event(
                logger,
                logging.WARNING,
                "llm.openrouter.request.failure",
                error_type=type(exc).__name__,
                status_code=exc.response.status_code,
                response_body=exc.response.text[:500],
            )
            raise
        except Exception as exc:
            log_event(logger, logging.WARNING, "llm.openrouter.request.failure", error_type=type(exc).__name__, error=str(exc))
            raise
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        if isinstance(content, dict):
            return content
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            log_event(
                logger,
                logging.WARNING,
                "llm.openrouter.response.parse_failure",
                error=str(exc),
                response_preview=content[:500],
            )
            raise

    def smoke_test(self) -> bool:
        try:
            result = self.complete_json('Return exactly this JSON object: {"ok": true}')
            return bool(result)
        except Exception as exc:
            log_event(logger, logging.WARNING, "llm.openrouter.smoke.failure", error_type=type(exc).__name__, error=str(exc))
            return False
