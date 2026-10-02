from sqlalchemy import Column, Integer, Float, String, ForeignKey, Index

from .base import Base


class Mastil(Base):
    __tablename__ = 'mastil'
    __table_args__ = (
        Index('idx_mastil_modelo3d', 'id_modelo2d'),
    )

    id_mastil = Column(Integer, primary_key=True, autoincrement=True)
    posicion_x = Column(Float, nullable=False)
    posicion_y = Column(Float, nullable=False)
    altura = Column(Float, nullable=False)
    tipo = Column(String(50), nullable=False)
    id_modelo2d = Column(
        Integer,
        ForeignKey('modelo2d.id_modelo2d', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False,
    )
    posicion_z = Column(Float, nullable=True)
    radio_cobertura = Column(Float, nullable=True)
