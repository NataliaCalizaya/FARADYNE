from pathlib import Path
from typing import Any, Dict

import fitz
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.proyecto import Proyecto
from app.repositories.mastil_repository import MastilRepository
from app.repositories.memoria_descriptiva_repository import MemoriaDescriptivaRepository
from app.repositories.nivel_proteccion_repository import NivelProteccionRepository
from app.repositories.resultado_simulacion_repository import ResultadoSimulacionRepository
from app.schemas.memoria_descriptiva_schema import MemoriaGenerateRequest, MemoriaResponse

router = APIRouter(prefix="/memorias", tags=["memoria descriptiva"])
OUTPUT_DIR = Path(__file__).resolve().parents[4] / "uploads" / "memorias"


def _proyecto_del_usuario(db: Session, id_proyecto: int, usuario: Dict[str, Any]) -> Dict[str, Any]:
    proyecto = db.get(Proyecto, id_proyecto)
    if proyecto is None or proyecto.id_usuario != usuario["id_usuario"]:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    return {c.name: getattr(proyecto, c.name) for c in proyecto.__table__.columns}


def _crear_pdf(proyecto: Dict[str, Any], nivel: Dict[str, Any], mastiles: list, resultado: Dict[str, Any], declaracion: bool) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"memoria-proyecto-{proyecto['id_proyecto']}.pdf"
    doc = fitz.open(); page = doc.new_page(); y = 60
    lineas = [
        "MEMORIA DESCRIPTIVA - SISTEMA DE PROTECCION CONTRA RAYOS",
        "",
        f"Proyecto: {proyecto['nombre']}", f"Cliente: {proyecto['cliente']}",
        f"Ubicacion: {proyecto['ubicacion']}", f"Fecha: {proyecto.get('fecha_del_proyecto') or proyecto.get('fecha_creacion')}",
        "", "1. Descripcion tecnica",
        "Se proyecta un Sistema de Proteccion contra Descargas Atmosfericas (SPDA) calculado mediante el metodo de la esfera rodante.",
        f"Nivel de proteccion: {nivel.get('nivel_proteccion', 'No definido')}",
        f"Radio de esfera: {nivel.get('radio_esfera', 'No definido')} m",
        f"Mastiles captores instalados: {len(mastiles)}",
        f"Cobertura calculada: {resultado.get('porcentaje_cobertura', 0)}%",
        "", "2. Declaracion de cumplimiento",
        "Se declara el cumplimiento del Decreto 351/79, Ley 19.587 e IRAM 2184." if declaracion else "La declaracion de cumplimiento legal no fue incluida.",
    ]
    for linea in lineas:
        page.insert_text((54, y), linea, fontsize=11 if y != 60 else 14)
        y += 22
    doc.save(path); doc.close()
    return path


@router.get("/proyecto/{id_proyecto}", response_model=MemoriaResponse)
def obtener_memoria(id_proyecto: int, db: Session = Depends(get_db), usuario: Dict[str, Any] = Depends(get_current_user)):
    _proyecto_del_usuario(db, id_proyecto, usuario)
    memoria = MemoriaDescriptivaRepository.get_por_proyecto(db, id_proyecto)
    if memoria is None:
        raise HTTPException(status_code=404, detail="Todavia no se generó una memoria para este proyecto.")
    return memoria


@router.post("/proyecto/{id_proyecto}/generar", response_model=MemoriaResponse)
def generar_memoria(id_proyecto: int, payload: MemoriaGenerateRequest, db: Session = Depends(get_db), usuario: Dict[str, Any] = Depends(get_current_user)):
    proyecto = _proyecto_del_usuario(db, id_proyecto, usuario)
    nivel = NivelProteccionRepository.get_nivel_proteccion_by_proyecto_id(db, id_proyecto) or {}
    mastiles = MastilRepository.get_mastiles_by_proyecto_id(db, id_proyecto)
    resultado = ResultadoSimulacionRepository.get_por_proyecto(db, id_proyecto) or {}
    archivo = _crear_pdf(proyecto, nivel, mastiles, resultado, payload.declaracion_decreto_351_79)
    return MemoriaDescriptivaRepository.upsert(db, id_proyecto, str(archivo), payload.declaracion_decreto_351_79)


@router.get("/proyecto/{id_proyecto}/descargar")
def descargar_memoria(id_proyecto: int, db: Session = Depends(get_db), usuario: Dict[str, Any] = Depends(get_current_user)):
    _proyecto_del_usuario(db, id_proyecto, usuario)
    memoria = MemoriaDescriptivaRepository.get_por_proyecto(db, id_proyecto)
    path = Path(memoria["ruta_pdf"]) if memoria and memoria.get("ruta_pdf") else None
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="No hay una memoria PDF generada.")
    return FileResponse(path, media_type="application/pdf", filename=path.name)
