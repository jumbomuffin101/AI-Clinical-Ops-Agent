from fastapi import APIRouter

from app.config import get_settings
from app.providers.openrouter import OpenRouterProvider

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/llm")
def llm_debug() -> dict:
    settings = get_settings()
    provider = settings.llm_provider.strip().lower() or "mock"
    api_key_loaded = bool(settings.openrouter_api_key)
    openrouter_configured = provider == "openrouter" and api_key_loaded
    provider_available = OpenRouterProvider().smoke_test() if openrouter_configured else False
    return {
        "provider": provider,
        "openrouter_configured": openrouter_configured,
        "api_key_loaded": api_key_loaded,
        "model": settings.openrouter_model,
        "app_name": settings.openrouter_app_name,
        "provider_available": provider_available,
    }
