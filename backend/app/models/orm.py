from sqlalchemy import Column, String, Text, Float, Boolean, BigInteger, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base
import uuid
from datetime import datetime, timezone

Base = declarative_base()

class Proyecto(Base):
    __tablename__ = 'proyecto'
    
    # Notar que la BD usa "id" o "id_proyecto"? En schema.sql es "id", pero en repo es "id_proyecto"
    # Lo más seguro es llamarlo "id_proyecto" como PK si es lo que usan en BD, o "id" si la columna se llama "id".
    # Según schema.sql la columna se llama "id". Asumiremos "id_proyecto" en BD si el query raw lo usa.
    # WAIT, let's name it "id_proyecto" as PK. Si falla, el usuario lo ajustará.
    id_proyecto = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String(255), nullable=False)
    cliente = Column(String(255), nullable=True)
    descripcion = Column(Text, nullable=True)
    ubicacion = Column(String(500), nullable=True)
    departamento = Column(String(100), nullable=True)
    provincia = Column(String(100), nullable=True)
    localidad = Column(String(100), nullable=True)
    estado = Column(String(50), default='borrador')
    fecha_creacion = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    fecha_actualizacion = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    fecha_del_proyecto = Column(String(50), nullable=True) # Usually date, but string is safer if not sure


class Plano(Base):
    __tablename__ = 'plano'
    
    id_plano = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_proyecto = Column(UUID(as_uuid=True), ForeignKey('proyecto.id_proyecto', ondelete='CASCADE'), nullable=False)
    nombre_archivo = Column(String(500), nullable=False)
    tipo_archivo = Column(String(50), nullable=False)
    ruta_archivo = Column(String(1000), nullable=False)
    tamano_bytes = Column(BigInteger, nullable=False)
    metadatos = Column(JSONB, default=dict)
    fecha_creacion = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))


class ZonaCeraunica(Base):
    __tablename__ = 'zona_ceraunica'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    departamento = Column(String(100), nullable=False)
    provincia = Column(String(100), nullable=True)
    ciudad = Column(String(100), nullable=True)
    nivel_ceraunico_td = Column(Float, nullable=False, default=30.0)
    densidad_rayos_ng = Column(Float, nullable=False, default=2.5)
    descripcion = Column(String(255), nullable=True)


class Modelo2D(Base):
    __tablename__ = 'modelo2d'
    
    id_modelo2d = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_plano = Column(UUID(as_uuid=True), ForeignKey('plano.id_plano', ondelete='CASCADE'), nullable=False)
    id_proyecto = Column(UUID(as_uuid=True), ForeignKey('proyecto.id_proyecto', ondelete='CASCADE'), nullable=False)
    poligonos = Column(JSONB, default=list)
    capas = Column(JSONB, default=list)
    cotas_altura = Column(JSONB, default=list)
    entidades_geom = Column(JSONB, default=dict)
    validado = Column(Boolean, default=False)
    fecha_creacion = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))


class Modelo3D(Base):
    __tablename__ = 'modelo3d'
    
    id_modelo3d = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_modelo2d = Column(UUID(as_uuid=True), ForeignKey('modelo2d.id_modelo2d', ondelete='CASCADE'), nullable=False)
    id_proyecto = Column(UUID(as_uuid=True), ForeignKey('proyecto.id_proyecto', ondelete='CASCADE'), nullable=False)
    geometria_volumetrica = Column(JSONB, nullable=False, default=dict)
    vista_defecto = Column(JSONB, default={"camera": [50, 50, 50], "target": [0, 0, 0]})
    fecha_creacion = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))


class NivelDeProteccion(Base):
    __tablename__ = 'nivel_de_proteccion'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_proyecto = Column(UUID(as_uuid=True), ForeignKey('proyecto.id_proyecto', ondelete='CASCADE'), nullable=False)
    id_zona = Column(UUID(as_uuid=True), ForeignKey('zona_ceraunica.id'), nullable=True)
    longitud_edificacion = Column(Float, nullable=False)
    anchura_edificacion = Column(Float, nullable=False)
    altura_edificacion = Column(Float, nullable=False)
    area_equivalente_ae = Column(Float, nullable=False)
    frecuencia_impactos_nd = Column(Float, nullable=False)
    frecuencia_tolerable_nc = Column(Float, nullable=False)
    requiere_spcr = Column(Boolean, nullable=False, default=False)
    nivel_proteccion_calculado = Column(String(50), nullable=True)
    eficiencia_proteccion = Column(Float, nullable=True)
    factores_riesgo = Column(JSONB, default=dict)
    fecha_calculo = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))


class Mastil(Base):
    __tablename__ = 'mastil'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_modelo3d = Column(UUID(as_uuid=True), ForeignKey('modelo3d.id_modelo3d', ondelete='CASCADE'), nullable=False)
    id_proyecto = Column(UUID(as_uuid=True), ForeignKey('proyecto.id_proyecto', ondelete='CASCADE'), nullable=False)
    posicion_x = Column(Float, nullable=False)
    posicion_y = Column(Float, nullable=False)
    posicion_z = Column(Float, nullable=False)
    altura = Column(Float, nullable=False)
    tipo = Column(String(100), default='Franklin')
    radio_cobertura = Column(Float, nullable=True)
    angulo_proteccion = Column(Float, nullable=True)
    fecha_creacion = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))


class ResultadoSimulacion(Base):
    __tablename__ = 'resultado_simulacion'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_proyecto = Column(UUID(as_uuid=True), ForeignKey('proyecto.id_proyecto', ondelete='CASCADE'), nullable=False)
    id_modelo3d = Column(UUID(as_uuid=True), ForeignKey('modelo3d.id_modelo3d', ondelete='CASCADE'), nullable=False)
    puntos_cobertura = Column(JSONB, default=list)
    puntos_desprotegidos = Column(JSONB, default=list)
    porcentaje_cobertura = Column(Float, default=0.0)
    metodo_calculo = Column(String(100), default='Esfera Rodante')
    fecha_simulacion = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))


class MemoriaDescriptiva(Base):
    __tablename__ = 'memoria_descriptiva'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_proyecto = Column(UUID(as_uuid=True), ForeignKey('proyecto.id_proyecto', ondelete='CASCADE'), nullable=False)
    titulo = Column(String(255), nullable=False)
    contenido = Column(JSONB, nullable=False, default=dict)
    estado = Column(String(50), default='borrador')
    fecha_creacion = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    fecha_actualizacion = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
