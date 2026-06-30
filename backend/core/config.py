from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/


class Settings(BaseSettings):
    # Auth
    JWT_SECRET: str
    JWT_ALGORITHM: str
    TIMEOUT_MINUTES: int = 30
    REFRESH_TIMEOUT_DAYS: int = 7
    VERIFICATION_TTL_HOURS: int = 24
    RESET_TTL_HOURS: int = 1
    # Per-user throttle on (re)issuing verification emails. Keyed on user_id so
    # it survives email/password changes.
    VERIFICATION_RESEND_COOLDOWN_MINUTES: int = 10
    # Separate, stricter throttle on actually *changing* the email address.
    EMAIL_CHANGE_COOLDOWN_HOURS: int = 24

    # Database
    DATABASE_URL: str = "sqlite:///./test.db"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # Email
    RESEND_API_KEY: str
    EMAIL_FROM: str = "noreply@ncplusplus.com"

    # Frontend
    FRONTEND_URL: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8")

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_cors_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


settings = Settings()