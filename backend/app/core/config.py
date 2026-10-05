from pathlib import Path
import os

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # Database Settings
    DB_HOST: str
    DB_PORT: int = 5432
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str
    DB_MIN_CONN: int = 1
    DB_MAX_CONN: int = 10

    # Application Settings
    APP_NAME: str = "FARADYNE Backend API"
    APP_ENV: str = "development"
    DEBUG: bool = True
    UPLOAD_DIR: str = "./uploads"

    # Auth Settings
    SECRET_KEY: str = "faradyne-clave-solo-para-desarrollo-cambiar-en-produccion"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    @field_validator("DEBUG", mode="before")
    @classmethod
    def normalizar_debug(cls, value):
        """Acepta etiquetas de entorno usadas por algunas terminales locales."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "production", "prod"}:
                return False
            if normalized in {"development", "dev", "debug"}:
                return True
        return value

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
