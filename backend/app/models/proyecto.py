from sqlalchemy import Column, Integer, String, Text, Date, ForeignKey, func
from .base import Base


class Proyecto(Base):
    __tablename__ = 'proyecto'

    id_proyecto = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(150), nullable=False)
    cliente = Column(String(150), nullable=False)
    ubicacion = Column(String(250), nullable=False)
    fecha_creacion = Column(Date, nullable=False, server_default=func.current_date())
    descripcion = Column(Text, nullable=True)
    departamento = Column(String(150), nullable=True)
    provincia = Column(String(150), nullable=True)
    localidad = Column(String(150), nullable=True)
    estado = Column(String(50), nullable=True, server_default='borrador')
    fecha_del_proyecto = Column(Date, nullable=True)
    id_usuario = Column(Integer, ForeignKey('usuario.id_usuario', ondelete='CASCADE'),nullable=True,index=True,)
