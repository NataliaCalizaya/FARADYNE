from sqlalchemy import Column, Integer, Float, Date, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB

from .base import Base


class Modelo3D(Base):
    __tablename__ = 'modelo3d'

    id_modelo3d = Column(Integer, primary_key=True, autoincrement=True)
    geometria_volumetrica = Column(JSONB, nullable=True)
    escala = Column(Float, nullable=True)
    creado_en = Column(Date, nullable=False, server_default=func.current_date())
    altura_h = Column(Float, nullable=True)
    id_modelo2d = Column(
        Integer,
        ForeignKey('modelo2d.id_modelo2d', ondelete='CASCADE'),
        nullable=False,
        unique=True,  # relación 1:1 con modelo2d
    )
    vista_defecto = Column(JSONB, nullable=True)
    actualizado_en = Column(DateTime, nullable=True)  # timestamp sin zona horaria
