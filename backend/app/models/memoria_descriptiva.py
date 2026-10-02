from sqlalchemy import Column, Integer, String, Boolean, Date, ForeignKey, func, text

from .base import Base


class MemoriaDescriptiva(Base):
    __tablename__ = 'memoria_descriptiva'

    id_memoria = Column(Integer, primary_key=True, autoincrement=True)
    ruta_pdf = Column(String(500), nullable=True)
    declaracion_decreto_351_79 = Column(Boolean, nullable=False, server_default=text('false'))
    fecha_generacion = Column(Date, nullable=False, server_default=func.current_date())
    id_proyecto = Column(
        Integer,
        ForeignKey('proyecto.id_proyecto', ondelete='CASCADE'),
        nullable=False,
        unique=True,  # una memoria por proyecto
    )
