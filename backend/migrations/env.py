from app.models.base import Base
import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import URL

# Carga el .env de la raíz del backend (donde está alembic.ini)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
from app.models.mastil import Mastil
from app.models.modelo2d import Modelo2D
from app.models.modelo3d import Modelo3D
from app.models.plano import Plano
from app.models.proyecto import Proyecto
from app.models.nivel_de_proteccion import NivelDeProteccion
from app.models.resultado_simulacion import ResultadoSimulacion
from app.models.zona_ceraunica import ZonaCeraunica

# 3. Asignas la metadata al target de Alembic
target_metadata = Base.metadata


def get_url() -> URL | str:
    # Opción 1: si tenés una URL completa en el .env
    if os.getenv("DATABASE_URL"):
        return os.getenv("DATABASE_URL")

    # Opción 2: variables sueltas (AJUSTÁ los nombres a los de tu .env)
    return URL.create(
        drivername="postgresql+psycopg2",   # si usás psycopg 3: "postgresql+psycopg"
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),  # URL.create escapa caracteres raros
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME"),
    )


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(get_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()