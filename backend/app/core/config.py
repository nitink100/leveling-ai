# app/core/config.py
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).parent.parent.parent

class Settings(BaseSettings):
    app_name: str = "LevelingAI"
    env: str = "local"
    DATABASE_URL: str

    # Supabase
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_STORAGE_BUCKET: str = "leveling-guides"
    SUPABASE_STORAGE_SIGNED_URL_TTL_SECONDS: int = 3600

    # =========================
    # LLM (Phase-1)
    # =========================
    LLM_PROVIDER: str = "gemini"   # future: openai, anthropic, etc.
    GEMINI_API_KEY: str | None = None

    # Default model (override per-call if needed)
    GEMINI_MODEL: str = "gemini-1.5-pro"

    # Runtime controls
    LLM_TIMEOUT_SECONDS: int = 30
    LLM_MAX_RETRIES: int = 2
    LLM_MAX_OUTPUT_TOKENS: int = 800
    LLM_TEMPERATURE: float = 0.4

    # Observability
    LLM_LOG_PROMPTS: bool = False  # keep False by default (avoid leaking data)

    model_config = SettingsConfigDict(
        env_file=os.path.join(PROJECT_ROOT, ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

settings = Settings()
