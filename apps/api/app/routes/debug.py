from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/llm")
def llm_debug() -> dict:
    settings = get_settings()
    provider = settings.llm_provider.strip().lower() or "mock"
    return {
        "provider": provider,
        "openrouter_configured": provider == "openrouter" and bool(settings.openrouter_api_key),
        "model": settings.openrouter_model,
        "api_key_loaded": bool(settings.openrouter_api_key),
    }
