from sqlalchemy import Column, Integer, String, Float

from .base import Base


class ZonaCeraunica(Base):
    __tablename__ = 'zona_ceraunica'

    id_zona = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(150), nullable=False)
    ng = Column(Float, nullable=False)
    ciudad = Column(String(150), nullable=False)
