import json

import httpx

from app.config import get_settings
from app.providers.base import BaseLLMProvider


class OpenRouterProvider(BaseLLMProvider):
    endpoint = "https://openrouter.ai/api/v1/chat/completions"

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
        response = httpx.post(self.endpoint, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        if isinstance(content, dict):
            return content
        return json.loads(content)
