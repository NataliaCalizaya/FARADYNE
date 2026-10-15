from sqlalchemy import Column, Integer, Float, String

from .base import Base


class MaterialCatalogo(Base):
    """Catálogo de materiales del cómputo de pararrayos.

    `clave` identifica el tipo de material (p. ej. 'mastil_galvanizado').
    `altura` solo aplica a materiales que varían por altura del mástil; NULL = vale para todas.
    `descripcion` es una referencia humana; el texto del listado lo arma el servicio.
    """

    __tablename__ = 'material_catalogo'

    id_material = Column(Integer, primary_key=True, autoincrement=True)
    clave = Column(String(50), nullable=False)
    altura = Column(Float, nullable=True)
    codigo = Column(String(30), nullable=True)
    descripcion = Column(String(200), nullable=False)
    unidad = Column(String(10), nullable=False, default='un')