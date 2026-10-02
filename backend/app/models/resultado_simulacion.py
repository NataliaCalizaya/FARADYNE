from sqlalchemy import Column, Integer, DateTime, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import JSONB

from .base import Base


class ResultadoSimulacion(Base):
    __tablename__ = 'resultado_simulacion'
    __table_args__ = (
        Index('idx_resultado_proyecto', 'id_proyecto'),
    )

    id_resultado = Column(Integer, primary_key=True, autoincrement=True)
    zonas_protegidas = Column(JSONB, nullable=True)
    zonas_vulnerables = Column(JSONB, nullable=True)
    mallas_cobertura = Column(JSONB, nullable=True)
    fecha_simulacion = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    id_proyecto = Column(
        Integer,
        ForeignKey('proyecto.id_proyecto', ondelete='CASCADE'),
        nullable=False,
    )
