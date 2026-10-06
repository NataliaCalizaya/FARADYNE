from sqlalchemy import Boolean, Column, DateTime, Integer, String, func, text

from .base import Base


class Usuario(Base):
    __tablename__ = 'usuario'

    id_usuario = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(150), nullable=False)
    email = Column(String(150), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    activo = Column(Boolean, nullable=False, server_default=text('true'))
    fecha_creacion = Column(DateTime, nullable=False, server_default=func.now())