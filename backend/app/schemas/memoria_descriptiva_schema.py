from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ImagenMemoria(BaseModel):
    """Imagen capturada en el frontend que el usuario eligió para el PDF.

    clave: 'plano' | 'iso' | 'iso_der' | 'caballera' | 'militar' | 'front' | 'top' | 'side'
    data_url: PNG o JPEG en base64 ('data:image/png;base64,...'). La validación fina
    (tipo, tamaño, base64) la hace memoria_pdf_service.decodificar_imagenes.
    """
    clave: str
    data_url: str


class MemoriaGenerateRequest(BaseModel):
    declaracion_decreto_351_79: bool = True
    # Solo las imágenes elegidas en la vista previa; vacío = PDF sin imágenes.
    imagenes: List[ImagenMemoria] = Field(default_factory=list)


class MemoriaResponse(BaseModel):
    id_memoria: int
    id_proyecto: int
    ruta_pdf: Optional[str] = None
    declaracion_decreto_351_79: bool
    fecha_generacion: date


# ──────────────────────────────────────────────────────────────────────────────
# Schema para el endpoint GET /memorias/proyecto/{id}/vista-previa
# ──────────────────────────────────────────────────────────────────────────────

class ProyectoPreview(BaseModel):
    id_proyecto: str
    nombre: Optional[str] = None
    cliente: Optional[str] = None
    ubicacion: Optional[str] = None
    departamento: Optional[str] = None
    provincia: Optional[str] = None
    localidad: Optional[str] = None
    descripcion: Optional[str] = None
    estado: Optional[str] = None
    fecha_del_proyecto: Optional[date] = None
    fecha_creacion: Optional[date] = None
    proyectista: Optional[str] = None   # nombre del usuario (si está disponible)


class ZonaCeraunicaPreview(BaseModel):
    id_zona: Optional[int] = None
    nombre: Optional[str] = None
    ciudad: Optional[str] = None
    ng: Optional[float] = None


class NivelProteccionPreview(BaseModel):
    nivel_proteccion: Optional[str] = None
    nivel_proteccion_recomendado: Optional[str] = None
    nd: Optional[float] = None
    nc: Optional[float] = None
    ae: Optional[float] = None
    eficiencia_minima: Optional[float] = None
    radio_esfera: Optional[float] = None
    factor_a_e: Optional[Dict[str, Any]] = None
    margen_lateral: Optional[float] = None
    longitud_edificacion: Optional[float] = None
    anchura_edificacion: Optional[float] = None
    altura_edificacion: Optional[float] = None
    zona_ceraunica: Optional[ZonaCeraunicaPreview] = None
    factores: Optional[Dict[str, Optional[float]]] = None   # {a, b, c, d, e}


class PrismaPreview(BaseModel):
    id: str
    estado: Optional[str] = None
    porcentaje_cobertura: Optional[float] = None


class TernaSinEsfera(BaseModel):
    motivo: Optional[str] = None
    mastiles: Optional[List[Any]] = None


class CoberturaPreview(BaseModel):
    porcentaje_cobertura: Optional[float] = None
    area_total_m2: Optional[float] = None
    area_protegida_m2: Optional[float] = None
    radio_esfera_rodante_r: Optional[float] = None
    total_mastiles: Optional[int] = None
    prismas: Optional[List[Dict[str, Any]]] = None
    triangulos_sin_esfera: Optional[List[Any]] = None
    advertencias: Optional[List[str]] = None
    zonas_desprotegidas: Optional[List[Dict[str, Any]]] = None


class MaterialItemPreview(BaseModel):
    codigo: Optional[str] = None
    descripcion: str
    cantidad: int
    unidad: str = "un"


class VistasPreviaIds(BaseModel):
    id_modelo2d: Optional[str] = None
    id_modelo3d: Optional[str] = None


class MemoriaVistaPrevia(BaseModel):
    """Respuesta completa del endpoint GET /memorias/proyecto/{id}/vista-previa."""
    proyecto: ProyectoPreview
    nivel_proteccion: Optional[NivelProteccionPreview] = None
    cobertura: Optional[CoberturaPreview] = None
    mastiles: Optional[List[Dict[str, Any]]] = None   # para los visores
    materiales: Optional[List[Dict[str, Any]]] = None
    total_mastiles_materiales: int = 0
    ids: VistasPreviaIds
    # Nota sobre origen de datos de cobertura
    cobertura_calculada_al_vuelo: bool = True
    # Respuesta completa de la cobertura, tal cual la usa el visor 3D del paso 5
    coverage_data: Optional[Dict[str, Any]] = None
