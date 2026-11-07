"""app.api.v1.endpoints.memoria_descriptiva

Endpoints para la Memoria Descriptiva del SPDA:
  GET  /memorias/proyecto/{id_proyecto}               → obtener memoria guardada
  POST /memorias/proyecto/{id_proyecto}/generar        → genera el PDF técnico final
                                                         (app.services.memoria_pdf_service) con las
                                                         imágenes que eligió el usuario
  GET  /memorias/proyecto/{id_proyecto}/descargar      → descarga el PDF
  GET  /memorias/proyecto/{id_proyecto}/vista-previa   → datos completos para la vista previa

El endpoint vista-previa:
  - Trae proyecto, nivel_de_proteccion, zona_ceraunica, ids modelo2d/3d.
  - Llama _calcular_cobertura (mismo código que usa el paso 5) para obtener
    prismas + triangulos_sin_esfera al vuelo: esos datos NO están guardados en
    resultado_simulacion (solo se guardan resúmenes). No recalcula por su cuenta:
    reutiliza exactamente la función del endpoint de cobertura.
  - Llama calcular_listado_materiales para la sección 6.
  - Devuelve los mástiles del modelo 2D activo para que los visores los usen.

Nota sobre listado de materiales: get_mastiles_by_proyecto_id trae TODOS los
mástiles del proyecto (todos los modelo2d). Si el proyecto tiene más de un
modelo2d, puede diferir del conteo de mástiles visibles en el paso 5
(que filtra por el modelo2d activo). Esta diferencia es intencional y se
preserva para mantener coherencia con el endpoint /materiales/proyecto/{id}.
"""
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.proyecto import Proyecto
from app.models.usuario import Usuario
from app.repositories.mastil_repository import MastilRepository
from app.repositories.material_repository import MaterialRepository
from app.repositories.memoria_descriptiva_repository import MemoriaDescriptivaRepository
from app.repositories.nivel_proteccion_repository import NivelProteccionRepository
from app.repositories.modelo3d_repository import Modelo3DRepository
from app.schemas.memoria_descriptiva_schema import (
    MemoriaGenerateRequest,
    MemoriaResponse,
    MemoriaVistaPrevia,
)
from app.services.material_list_service import calcular_listado_materiales
from app.services.memoria_pdf_service import decodificar_imagenes, generar_memoria_pdf

# Importamos _calcular_cobertura para reutilizarla exactamente igual que el paso 5
from app.api.v1.endpoints.cobertura import _calcular_cobertura

router = APIRouter(prefix="/memorias", tags=["memoria descriptiva"])
OUTPUT_DIR = Path(__file__).resolve().parents[4] / "uploads" / "memorias"


def _proyecto_del_usuario(db: Session, id_proyecto: int, usuario: Dict[str, Any]) -> Dict[str, Any]:
    proyecto = db.get(Proyecto, id_proyecto)
    if proyecto is None or proyecto.id_usuario != usuario["id_usuario"]:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    return {c.name: getattr(proyecto, c.name) for c in proyecto.__table__.columns}


@router.get("/proyecto/{id_proyecto}", response_model=MemoriaResponse)
def obtener_memoria(id_proyecto: int, db: Session = Depends(get_db), usuario: Dict[str, Any] = Depends(get_current_user)):
    _proyecto_del_usuario(db, id_proyecto, usuario)
    memoria = MemoriaDescriptivaRepository.get_por_proyecto(db, id_proyecto)
    if memoria is None:
        raise HTTPException(status_code=404, detail="Todavia no se generó una memoria para este proyecto.")
    return memoria


@router.post("/proyecto/{id_proyecto}/generar", response_model=MemoriaResponse)
def generar_memoria(id_proyecto: int, payload: MemoriaGenerateRequest, db: Session = Depends(get_db), usuario: Dict[str, Any] = Depends(get_current_user)):
    """Genera el PDF técnico final.

    Los datos salen de _armar_vista_previa (la misma función que la vista previa, así el
    PDF muestra exactamente lo que ve el usuario) y las imágenes son las que eligió en el
    frontend. No se recalcula nada por separado.
    """
    proyecto = _proyecto_del_usuario(db, id_proyecto, usuario)
    datos = _armar_vista_previa(db, id_proyecto, proyecto)
    datos.pop("coverage_data", None)  # solo lo necesita el visor 3D; el PDF no lo usa

    try:
        imagenes = decodificar_imagenes([i.model_dump() for i in payload.imagenes])
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    ruta = OUTPUT_DIR / f"memoria-proyecto-{id_proyecto}.pdf"
    try:
        generar_memoria_pdf(ruta, datos, imagenes, payload.declaracion_decreto_351_79)
    except (FileNotFoundError, RuntimeError) as e:
        raise HTTPException(status_code=500, detail=f"No se pudo generar el PDF: {e}")
    return MemoriaDescriptivaRepository.upsert(db, id_proyecto, str(ruta), payload.declaracion_decreto_351_79)


@router.get("/proyecto/{id_proyecto}/descargar")
def descargar_memoria(id_proyecto: int, db: Session = Depends(get_db), usuario: Dict[str, Any] = Depends(get_current_user)):
    _proyecto_del_usuario(db, id_proyecto, usuario)
    memoria = MemoriaDescriptivaRepository.get_por_proyecto(db, id_proyecto)
    path = Path(memoria["ruta_pdf"]) if memoria and memoria.get("ruta_pdf") else None
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="No hay una memoria PDF generada.")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


def _armar_vista_previa(db: Session, id_proyecto: int, proyecto_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Arma todos los datos de la memoria descriptiva (vista previa y PDF):
      - Datos del proyecto (sección 1)
      - Nivel de protección y zona ceráunica (sección 2)
      - IDs de modelo2d/3d y mástiles del modelo2d activo (secciones 3 y 4)
      - Cobertura calculada al vuelo con la misma lógica del paso 5 (sección 5)
      - Listado de materiales (sección 6)
    """
    # ── Proyectista (nombre del usuario propietario) ──────────────────────────
    proyectista = None
    try:
        if proyecto_dict.get("id_usuario"):
            u = db.get(Usuario, proyecto_dict["id_usuario"])
            if u:
                proyectista = u.nombre
    except Exception:
        pass

    # ── Nivel de protección + zona ceráunica ─────────────────────────────────
    nivel_db = NivelProteccionRepository.get_nivel_proteccion_by_proyecto_id(db, id_proyecto)
    nivel_out: Dict[str, Any] = {}
    if nivel_db:
        nivel_out = {k: v for k, v in nivel_db.items()}
        crudo = nivel_db.get("factores_riesgo") or nivel_db.get("factor_a_e") or {}
        nivel_out["factores"] = {
            k: (crudo.get(k, crudo.get(f"factor_{k}")) if isinstance(crudo, dict) else None)
            or nivel_db.get(f"factor_{k}")
            for k in "abcde"
        }
        # Zona ceráunica asociada
        id_zona = nivel_db.get("id_zona")
        if id_zona:
            zona = NivelProteccionRepository.get_zona_ceraunica_by_id(db, id_zona)
            nivel_out["zona_ceraunica"] = zona or {}
        else:
            nivel_out["zona_ceraunica"] = {}

    # ── Modelo 2D y 3D activos (el mismo par que usa Workspace/UbicacionMastiles) ──
    # Usamos Modelo3DRepository.get_modelo3d_by_proyecto_id que devuelve el más
    # reciente (igual que el endpoint completo de proyecto).
    modelo3d_db = Modelo3DRepository.get_modelo3d_by_proyecto_id(db, id_proyecto)
    id_modelo2d: int | None = modelo3d_db.get("id_modelo2d") if modelo3d_db else None
    id_modelo3d: int | None = modelo3d_db.get("id_modelo3d") if modelo3d_db else None

    # ── Mástiles del modelo2d activo (para los visores) ───────────────────────
    mastiles_visor: list = []
    if id_modelo2d:
        mastiles_visor = MastilRepository.get_mastiles_by_modelo2d_id(db, id_modelo2d)

    # ── Cobertura (misma lógica que GET /cobertura/proyecto/{id}) ─────────────
    # Los datos de prismas + triangulos_sin_esfera no están en la BD:
    # se calculan al vuelo reutilizando _calcular_cobertura.
    cobertura_out: Dict[str, Any] = {}
    # Respuesta completa de la cobertura (incluye superficies_esfera, etc.): es lo
    # que necesita Modelo3DViewer como coverageData para dibujar esferas y zonas.
    coverage_full: Dict[str, Any] | None = None
    try:
        calculo = _calcular_cobertura(db, id_proyecto)
        resp = calculo["respuesta"]
        coverage_full = resp
        cobertura_out = {
            "porcentaje_cobertura": resp.get("porcentaje_cobertura"),
            "area_total_m2": resp.get("area_total_m2"),
            "area_protegida_m2": resp.get("area_protegida_m2"),
            "radio_esfera_rodante_r": resp.get("radio_esfera_rodante_r"),
            "total_mastiles": resp.get("total_mastiles"),
            "prismas": resp.get("prismas", []),
            "triangulos_sin_esfera": resp.get("triangulos_sin_esfera", []),
            "advertencias": resp.get("advertencias", []),
            "zonas_desprotegidas": resp.get("zonas_desprotegidas", []),
        }
    except Exception:
        cobertura_out = {}

    # ── Materiales (todos los mástiles del proyecto, igual que el paso 6) ─────
    mastiles_proyecto = MastilRepository.get_mastiles_by_proyecto_id(db, id_proyecto)
    catalogo = MaterialRepository.get_codigos(db)
    items_materiales = calcular_listado_materiales(mastiles_proyecto, catalogo)

    return {
        "proyecto": {
            "id_proyecto": str(id_proyecto),
            "nombre": proyecto_dict.get("nombre"),
            "cliente": proyecto_dict.get("cliente"),
            "ubicacion": proyecto_dict.get("ubicacion"),
            "departamento": proyecto_dict.get("departamento"),
            "provincia": proyecto_dict.get("provincia"),
            "localidad": proyecto_dict.get("localidad"),
            "descripcion": proyecto_dict.get("descripcion"),
            "estado": proyecto_dict.get("estado"),
            "fecha_del_proyecto": proyecto_dict.get("fecha_del_proyecto"),
            "fecha_creacion": proyecto_dict.get("fecha_creacion"),
            "proyectista": proyectista,
        },
        "nivel_proteccion": nivel_out if nivel_out else None,
        "cobertura": cobertura_out if cobertura_out else None,
        "mastiles": mastiles_visor,
        "materiales": items_materiales,
        "total_mastiles_materiales": len(mastiles_proyecto),
        "ids": {
            "id_modelo2d": str(id_modelo2d) if id_modelo2d else None,
            "id_modelo3d": str(id_modelo3d) if id_modelo3d else None,
        },
        "cobertura_calculada_al_vuelo": True,
        "coverage_data": coverage_full,
    }


@router.get("/proyecto/{id_proyecto}/vista-previa", response_model=MemoriaVistaPrevia)
def vista_previa_memoria(
    id_proyecto: int,
    db: Session = Depends(get_db),
    usuario: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Datos completos para renderizar la vista previa de la Memoria Descriptiva."""
    proyecto_dict = _proyecto_del_usuario(db, id_proyecto, usuario)
    return _armar_vista_previa(db, id_proyecto, proyecto_dict)
