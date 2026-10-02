import logging
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

logger = logging.getLogger("faradyne.database")

# 1. Construir la URL de conexión a partir de tus settings
SQLALCHEMY_DATABASE_URL = (
    f"postgresql+psycopg2://{settings.DB_USER}:{settings.DB_PASSWORD}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
)

# 2. Crear el Engine de SQLAlchemy
# pool_pre_ping=True verifica si la conexión está viva antes de usarla (reemplaza tu validación inicial de SELECT 1)
# pool_size y max_overflow manejan el minconn y maxconn
try:
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_pre_ping=True,
        pool_size=getattr(settings, "DB_MIN_CONN", 5),
        max_overflow=getattr(settings, "DB_MAX_CONN", 10) - getattr(settings, "DB_MIN_CONN", 5)
    )
    logger.info(f"Conexión a PostgreSQL configurada en {settings.DB_HOST}:{settings.DB_PORT}")
except Exception as e:
    logger.critical(f"FATAL: Error al configurar el motor de base de datos: {e}")
    raise e

# 3. Configurar la fábrica de sesiones
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. Dependencia para inyectar en FastAPI
def get_db() -> Generator:
    """
    Provee una sesión de base de datos a los endpoints de FastAPI y la cierra automáticamente.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
