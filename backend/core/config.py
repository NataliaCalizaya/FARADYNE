from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = 'FARADYNE'
    APP_VERSION: str = '0.1.0'
    DEBUG: bool = True
    DATABASE_URL: str = 'sqlite:///./test.db'
    SECRET_KEY: str = 'dev-secret-key-change-in-production'
    ALGORITHM: str = 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    UPLOAD_DIR: str = '/tmp/faradyne_uploads'
    MAX_FILE_SIZE_MB: int = 100
    ALLOWED_EXTENSIONS: list[str] = ['.dxf', '.dwg', '.pdf', '.png', '.jpg', '.jpeg']

settings = Settings()
