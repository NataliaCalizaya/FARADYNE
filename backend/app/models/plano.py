from sqlalchemy import (
    Column, Integer, String, Date, ForeignKey, CheckConstraint, Index, func, text
)
from sqlalchemy.dialects.postgresql import JSONB

from .base import Base


class Plano(Base):
    __tablename__ = 'plano'
    __table_args__ = (
        CheckConstraint(
            "tipo_archivo IN ('DXF', 'PDF')",
            name='plano_tipo_archivo_check',
        ),
        Index('idx_plano_proyecto', 'id_proyecto'),
    )

    id_plano = Column(Integer, primary_key=True, autoincrement=True)
    nombre_archivo = Column(String(150), nullable=False)
    tipo_archivo = Column(String(20), nullable=False)
    ruta_archivo = Column(String(500), nullable=False)
    fecha_carga = Column(Date, nullable=False, server_default=func.current_date())
    id_proyecto = Column(
        Integer,
        ForeignKey('proyecto.id_proyecto', ondelete='CASCADE'),
        nullable=False,
    )
    tamano_bytes = Column(Integer, nullable=True, server_default=text('0'))
    metadatos = Column(JSONB, nullable=True, server_default=text("'{}'::jsonb"))
