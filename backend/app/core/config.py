import os
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

# Walk up from this file to find the project root .env
_ROOT = Path(__file__).resolve().parents[3]  # backend/app/core/config.py -> project root
_ENV_FILE = _ROOT / ".env" if (_ROOT / ".env").exists() else ".env"


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    # Database
    database_url: str = ""

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"

    # AI APIs — only 2 keys needed
    gemini_api_key: str = ""    # Powers: prompt refinement, image gen (Imagen 3), video gen (Veo 2)
    freepik_api_key: str = ""   # Powers: image gen (Magnific/Mystic), video gen (Freepik Video)

    class Config:
        env_file = str(_ENV_FILE)
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
