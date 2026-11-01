from sqlalchemy import Column, Integer, Boolean, ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB

from .base import Base


class Modelo2D(Base):
    __tablename__ = 'modelo2d'

    id_modelo2d = Column(Integer, primary_key=True, autoincrement=True)

    # Cada polígono de `poligonos` puede incluir "nivel_superficie": la cota
    # en el centro del polígono (número) o None. Junto con los niveles de dos
    # lados genera la cubierta parabólica; el tipo de techo NO se guarda, se
    # deduce de estos datos. Al ser JSONB no requiere migración: si el campo
    # falta, el comportamiento es el anterior.
    poligonos = Column(JSONB, nullable=True)
    lineas = Column(JSONB, nullable=True)
    capas = Column(JSONB, nullable=True)
    colores = Column(JSONB, nullable=True)
    cotas_altura = Column(JSONB, nullable=True)
    validado = Column(Boolean, nullable=False, server_default=text('false'))
    id_plano = Column(
        Integer,
        ForeignKey('plano.id_plano', ondelete='CASCADE'),
        nullable=False,
        unique=True,  # relación 1:1 con plano
    )
