from sqlalchemy import Column, Integer, Float, String, Index, text

from .base import Base


class MaterialCatalogo(Base):
    """... (tu docstring igual) ..."""

    __tablename__ = 'material_catalogo'

    id_material = Column(Integer, primary_key=True, autoincrement=True)
    clave = Column(String(50), nullable=False)
    altura = Column(Float, nullable=True)
    codigo = Column(String(30), nullable=True)
    descripcion = Column(String(200), nullable=False)
    unidad = Column(String(10), nullable=False, default='un', server_default='un')

    __table_args__ = (
        Index('uq_material_clave_altura', 'clave', 'altura',
              unique=True, postgresql_where=text('altura IS NOT NULL')),
        Index('uq_material_clave_sin_altura', 'clave',
              unique=True, postgresql_where=text('altura IS NULL')),
    )
