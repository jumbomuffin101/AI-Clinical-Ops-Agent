from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Clinical Ops Agent API"
    environment: str = "local"
    llm_provider: str = "mock"
    openai_api_key: str = ""
    groq_enabled: bool = True
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    openrouter_api_key: str = ""
    openrouter_enabled: bool = True
    openrouter_model: str = "qwen/qwen-2.5-72b-instruct:free"
    openrouter_fallback_models: str = ""
    openrouter_site_url: str = ""
    openrouter_app_name: str = "AI Clinical Ops Agent"
    database_url: str = "sqlite:///./clinical_ops.db"
    cors_origins: str = "http://localhost:3000"
    auto_create_tables: bool = True
    max_request_bytes: int = 262144
    project_root: Path = Path(__file__).resolve().parents[3]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def reference_docs_path(self) -> Path:
        return self.project_root / "data" / "reference_docs"

    @property
    def fee_schedule_path(self) -> Path:
        return self.project_root / "data" / "fee_schedule" / "fee_schedule.json"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def openrouter_fallback_model_list(self) -> list[str]:
        return [model.strip() for model in self.openrouter_fallback_models.split(",") if model.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
