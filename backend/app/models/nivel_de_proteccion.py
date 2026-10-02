from sqlalchemy import Column, Integer, String, Float, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB

from .base import Base


class NivelDeProteccion(Base):
    __tablename__ = 'nivel_de_proteccion'
    __table_args__ = (
        CheckConstraint(
            "nivel_proteccion IN ('I', 'II', 'III', 'IV')",
            name='nivel_de_proteccion_nivel_check',
        ),
    )

    id_nivel_proteccion = Column(Integer, primary_key=True, autoincrement=True)
    nivel_proteccion = Column(String(5), nullable=False)
    nd = Column(Float, nullable=True)
    nc = Column(Float, nullable=True)
    ae = Column(Float, nullable=True)
    eficiencia_minima = Column(Float, nullable=True)
    radio_esfera = Column(Float, nullable=True)
    factor_a_e = Column(JSONB, nullable=True)
    margen_lateral = Column(Float, nullable=True)
    id_proyecto = Column(
        Integer,
        ForeignKey('proyecto.id_proyecto', ondelete='CASCADE'),
        nullable=False,
        unique=True,  # un cálculo por proyecto
    )
    id_zona = Column(Integer, ForeignKey('zona_ceraunica.id_zona'), nullable=True)
    longitud_edificacion = Column(Float, nullable=True)
    anchura_edificacion = Column(Float, nullable=True)
    altura_edificacion = Column(Float, nullable=True)
    nivel_proteccion_recomendado = Column(String(5), nullable=True)
