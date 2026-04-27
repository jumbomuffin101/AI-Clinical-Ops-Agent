from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import text

from app.config import get_settings
from app.db.session import SessionLocal

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.environment,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/health/db")
def database_health() -> dict[str, str]:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        database = "ok"
        status = "ok"
    except Exception:
        database = "unavailable"
        status = "degraded"

    return {
        "status": status,
        "database": database,
        "environment": settings.environment,
        "timestamp": datetime.now(UTC).isoformat(),
    }
