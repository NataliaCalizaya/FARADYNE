import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database Settings
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "faradyne"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    DB_MIN_CONN: int = 1
    DB_MAX_CONN: int = 10

    # Application Settings
    APP_NAME: str = "FARADYNE Backend API"
    APP_ENV: str = "development"
    DEBUG: bool = True
    UPLOAD_DIR: str = "./uploads"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
