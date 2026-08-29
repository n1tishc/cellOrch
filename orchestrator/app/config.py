"""Centralized, validated application settings.

All environment variables are declared here with typed defaults so the rest of
the codebase can import a single `settings` object instead of reading
`os.environ` directly.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    db_url: str = "sqlite:///cellflow.db"
    cv_service_url: str = "http://cv-service:8001"

    clock_factor: float = 4.0
    failure_rate: float = 0.05
    max_retries: int = 2
    backoff_s: float = 2.0

    tick_interval: float = 1.0
    seed_on_start: int = 10

    confluence_threshold: float = 0.80
    max_passages: int = 3


settings = Settings()
