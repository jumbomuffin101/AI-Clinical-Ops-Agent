from fastapi import APIRouter

from app.config import get_settings
from app.providers.openrouter import OpenRouterProvider

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/llm")
def llm_debug(smoke: bool = False) -> dict:
    settings = get_settings()
    provider = settings.llm_provider.strip().lower() or "mock"
    api_key_loaded = bool(settings.openrouter_api_key)
    provider_configured = provider == "openrouter" and settings.openrouter_enabled and api_key_loaded
    provider_available = OpenRouterProvider().smoke_test() if smoke and provider_configured else None
    return {
        "provider": provider,
        "api_key_loaded": api_key_loaded,
        "primary_model": settings.openrouter_model,
        "fallback_models": settings.openrouter_fallback_model_list,
        "app_name": settings.openrouter_app_name,
        "provider_configured": provider_configured,
        "smoke_test_run": smoke and provider_configured,
        "provider_available": provider_available,
    }
