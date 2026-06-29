from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/


class Settings(BaseSettings):
    JWT_SECRET: str
    JWT_ALGORITHM: str
    TIMEOUT_MINUTES: int = 30
    DATABASE_URL: str = "sqlite:///./test.db"
    REFRESH_TIMEOUT_DAYS: int = 7
    # Comma-separated list of allowed frontend origins, e.g.
    # CORS_ORIGINS=http://localhost:5173,https://app.example.com
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8")

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_cors_origins(cls, v: object) -> object:
        # Allow a plain comma-separated env string (pydantic-settings otherwise
        # expects JSON for list-typed fields).
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


settings = Settings()
