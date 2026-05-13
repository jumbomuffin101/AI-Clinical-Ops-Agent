from fastapi import APIRouter

from app.config import get_settings
from app.providers.groq import GroqProvider
from app.providers.openrouter import OpenRouterProvider

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/llm")
def llm_debug(smoke: bool = False) -> dict:
    settings = get_settings()
    provider = settings.llm_provider.strip().lower() or "mock"
    api_key_loaded = _api_key_loaded(provider)
    provider_configured = _provider_configured(provider)
    provider_available = _smoke_test(provider) if smoke and provider_configured else None
    return {
        "provider": provider,
        "provider_configured": provider_configured,
        "fallback_models": settings.openrouter_fallback_model_list,
        "provider_available": provider_available,
        "model": _model(provider),
        "primary_model": _model(provider),
        "ai_enabled": _enabled(provider),
        "api_key_loaded": api_key_loaded,
        "app_name": settings.openrouter_app_name,
        "smoke_test_run": smoke and provider_configured,
    }


def _enabled(provider: str) -> bool:
    settings = get_settings()
    if provider == "groq":
        return settings.groq_enabled
    if provider == "openrouter":
        return settings.openrouter_enabled
    return False


def _api_key_loaded(provider: str) -> bool:
    settings = get_settings()
    if provider == "groq":
        return bool(settings.groq_api_key)
    if provider == "openrouter":
        return bool(settings.openrouter_api_key)
    return False


def _provider_configured(provider: str) -> bool:
    return provider in {"groq", "openrouter"} and _enabled(provider) and _api_key_loaded(provider)


def _model(provider: str) -> str:
    settings = get_settings()
    if provider == "groq":
        return settings.groq_model
    if provider == "openrouter":
        return settings.openrouter_model
    return ""


def _smoke_test(provider: str) -> bool:
    if provider == "groq":
        return GroqProvider().smoke_test()
    if provider == "openrouter":
        return OpenRouterProvider().smoke_test()
    return False
