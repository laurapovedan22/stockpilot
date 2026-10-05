from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://stockpilot:stockpilot@localhost:5432/stockpilot"
    app_mode: Literal["local", "public_demo"] = "local"
    cors_origins: str = "http://localhost:5173"
    artifact_dir: str = "../artifacts"
    upload_dir: str = "uploads"
    max_csv_bytes: int = 10 * 1024 * 1024
    openai_api_key: str = ""
    openai_model: str = ""
    ai_enabled: bool = False
    ai_timeout_seconds: int = Field(default=20, ge=1, le=120)
    random_seed: int = 42
    log_level: str = "INFO"


settings = Settings()
