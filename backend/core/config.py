from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/


class Settings(BaseSettings):
    JWT_SECRET: str
    JWT_ALGORITHM: str
    TIMEOUT_MINUTES: int = 30
    DATABASE_URL: str = "sqlite:///./test.db"
    REFRESH_TIMEOUT_DAYS: int = 7

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8")


settings = Settings()
