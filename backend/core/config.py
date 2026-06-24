from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    JWT_SECRET: str
    JWT_ALGORITHM: str
    TIMEOUT_MINUTES: int = 30
    DATABASE_URL: str = "sqlite:///./test.db"

    model_config = SettingsConfigDict(env_file="backend/.env", env_file_encoding="utf-8")


settings = Settings()
