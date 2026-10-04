import os
import uuid
from contextlib import suppress
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.repositories.plano_repository import PlanoRepository
from app.schemas.plano_schema import PlanoCreateResponse, PlanoPreviewResponse
from app.services.dxf_interpreter_service import DXFInterpreterService
from app.services.editor_modelo2d_service import EditorModelo2DService
from app.services.niveles_utils import NivelesUtils
from app.services.pdf_interpreter_service import PDFInterpreterService

router = APIRouter(prefix="/planos", tags=["HU02 - Planos"])
modelos2d_router = APIRouter(prefix="/modelos2d", tags=["HU02 - Modelo 2D"])


# ============================================================
# UTILIDADES
# ============================================================


def _http_error(err: ValueError) -> HTTPException:
    """El editor informa todo con ValueError: 'No se encontró...' -> 404, resto -> 400."""
    detalle = str(err)
    codigo = (
        status.HTTP_404_NOT_FOUND
        if detalle.startswith("No se encontró")
        else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(status_code=codigo, detail=detalle)


def _buscar_por_id(items: Optional[List[Dict[str, Any]]], item_id: str) -> Optional[Dict[str, Any]]:
    return next((i for i in (items or []) if str(i.get("id")) == str(item_id)), None)


# ============================================================
# PLANOS
# ============================================================


@router.post("", response_model=PlanoCreateResponse, status_code=status.HTTP_201_CREATED)
async def upload_plano(
    file: UploadFile = File(...),
    idProyecto: int = Form(..., description="ID del proyecto asociado"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """HU02: carga e interpretación de un plano DXF o PDF.

        archivo -> intérprete -> Modelo 2D -> persistencia
    """
    if not PlanoRepository.get_proyecto_by_id(db, idProyecto):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el proyecto '{idProyecto}'.",
        )

    filename = file.filename or "plano_sin_nombre"
    ext = os.path.splitext(filename)[1].lower()

    if ext not in (".dxf", ".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato no soportado '{ext}'. Solo se admiten archivos .dxf y .pdf.",
        )

    file_bytes = await file.read()
    tamano_bytes = len(file_bytes)

    if tamano_bytes == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo subido está vacío.",
        )

    unique_filename = f"{uuid.uuid4().hex}_{filename}"
    saved_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    # INTERPRETACIÓN
    try:
        if ext == ".dxf":
            doc = DXFInterpreterService.validate_and_read_dxf(file_bytes, filename)
            parsed_data = DXFInterpreterService.interpret_dxf_data(doc)
        else:
            doc = PDFInterpreterService.validate_and_read_pdf(file_bytes, filename)
            parsed_data = PDFInterpreterService.interpret_pdf_data(doc, file_bytes=file_bytes)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    # GUARDAR ARCHIVO
    try:
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        with open(saved_path, "wb") as f:
            f.write(file_bytes)
    except Exception as io_err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al guardar el archivo en el servidor: {io_err}",
        )

    # GUARDAR PLANO + MODELO 2D (si la BD falla, no queda el archivo huérfano)
    try:
        plano_db = PlanoRepository.create_plano(
            db,
            id_proyecto=idProyecto,
            nombre_archivo=filename,
            tipo_archivo=ext.replace(".", "").upper(),
            ruta_archivo=saved_path,
            tamano_bytes=tamano_bytes,
            metadatos={"bounding_box": parsed_data.get("bounding_box", {})},
        )
        id_plano = plano_db["id_plano"]

        modelo2d_db = PlanoRepository.create_modelo2d(
            db,
            id_plano=id_plano,
            poligonos=parsed_data.get("poligonos", []),
            capas=parsed_data.get("capas", []),
            cotas_altura=parsed_data.get("cotas_altura", []),
            lineas=parsed_data.get("lineas", []),
        )
    except Exception:
        with suppress(OSError):
            os.remove(saved_path)
        raise

    return {
        "id": str(id_plano),
        "id_proyecto": str(idProyecto),
        "nombre_archivo": filename,
        "tipo_archivo": ext.replace(".", ""),
        "ruta_archivo": saved_path,
        "tamano_bytes": tamano_bytes,
        "metadatos": plano_db.get("metadatos", {}),
        "fecha_creacion": plano_db.get("fecha_carga") or plano_db.get("fecha_creacion"),
        "id_modelo2d": str(modelo2d_db["id_modelo2d"]),
    }


@router.get("/{id}/preview", response_model=PlanoPreviewResponse)
def get_plano_preview(id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Todo lo que necesita el visor para dibujar el plano."""
    plano = PlanoRepository.get_plano_by_id(db, id)
    if not plano:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el plano con ID '{id}'.",
        )

    modelo2d = PlanoRepository.get_modelo2d_by_plano_id(db, id) or {}
    poligonos = modelo2d.get("poligonos") or []
    cotas_altura = modelo2d.get("cotas_altura") or []

    # Migración en memoria de modelos guardados con el formato anterior.
    NivelesUtils.migrar_formato_anterior(poligonos, cotas_altura)

    metadatos = plano.get("metadatos") or {}
    id_modelo2d = modelo2d.get("id_modelo2d")

    return {
        "id": str(plano.get("id_plano", id)),
        "id_proyecto": str(plano.get("id_proyecto", "")),
        "nombre_archivo": plano.get("nombre_archivo", ""),
        "tipo_archivo": plano.get("tipo_archivo", ""),
        "ruta_archivo": plano.get("ruta_archivo", ""),
        "bounding_box": metadatos.get("bounding_box", {}),
        "id_modelo2d": str(id_modelo2d) if id_modelo2d is not None else None,
        "validado": bool(modelo2d.get("validado", False)),
        "capas": modelo2d.get("capas") or [],
        "cotas_altura": cotas_altura,
        "poligonos": poligonos,
        "lineas": modelo2d.get("lineas") or [],
    }


# ============================================================
# MODELO 2D - OBTENER / ACTUALIZAR
# ============================================================


@modelos2d_router.get("/{id}")
def get_modelo2d(id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    try:
        return EditorModelo2DService.obtener_modelo2d(db, id)
    except ValueError as err:
        raise _http_error(err)


@modelos2d_router.get("/{id}/edicion")
def get_modelo2d_edicion(
    id: int, incluir_lineas: bool = False, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    try:
        modelo = EditorModelo2DService.obtener_modelo2d(db, id)
    except ValueError as err:
        raise _http_error(err)

    resultado = {
        "id_modelo2d": str(id),
        "validado": bool(modelo.get("validado", False)),
        "capas": modelo.get("capas") or [],
        "poligonos": modelo.get("poligonos") or [],
        "cotas_altura": modelo.get("cotas_altura") or [],
    }
    if incluir_lineas:
        resultado["lineas"] = modelo.get("lineas") or []
    return resultado

@modelos2d_router.patch("/{id}")
def update_modelo2d_endpoint(
    id: int,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Actualización general del Modelo2D (compatibilidad)."""
    updated = PlanoRepository.update_modelo2d(
        id_modelo2d=id,
        poligonos=payload.get("poligonos"),
        lineas=payload.get("lineas"),
        capas=payload.get("capas"),
        cotas_altura=payload.get("cotas_altura"),
        colores=payload.get("colores"),
        validado=payload.get("validado"),
    )
    if not updated:  # update_modelo2d devuelve None si no existe
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el Modelo 2D con ID '{id}'.",
        )

    return {
        "id": str(updated.get("id_modelo2d", id)),
        "id_plano": str(updated.get("id_plano", "")),
        "validado": bool(updated.get("validado", False)),
        "poligonos": updated.get("poligonos", []),
        "lineas": updated.get("lineas", []),
        "capas": updated.get("capas", []),
        "cotas_altura": updated.get("cotas_altura", []),
        "colores": updated.get("colores", []),
        "mensaje": "Modelo 2D actualizado correctamente.",
    }


# ============================================================
# SUPERFICIES NUEVAS
# ============================================================


@modelos2d_router.post("/{id}/triangulos")
def create_triangulo(
    id: int, payload: Dict[str, Any] = Body(...), db: Session = Depends(get_db)
) -> Dict[str, Any]:
    try:
        if "puntos" not in payload:
            raise ValueError("El campo 'puntos' es obligatorio.")

        poligono = EditorModelo2DService.crear_triangulo(
            db,
            id_modelo2d=id,
            puntos=payload["puntos"],
            capa=payload.get("capa"),
            page=payload.get("page", 0),
            tipo_cubierta=payload.get("tipo_cubierta", "pendiente_por_resolver"),
        )
        return {"mensaje": "Triángulo creado correctamente.", "poligono": poligono}
    except ValueError as err:
        raise _http_error(err)


@modelos2d_router.post("/{id}/rectangulos")
def create_rectangulo(
    id: int, payload: Dict[str, Any] = Body(...), db: Session = Depends(get_db)
) -> Dict[str, Any]:
    try:
        poligono = EditorModelo2DService.crear_rectangulo(
            db,
            id_modelo2d=id,
            x1=float(payload["x1"]),
            y1=float(payload["y1"]),
            x2=float(payload["x2"]),
            y2=float(payload["y2"]),
            capa=payload.get("capa"),
            page=payload.get("page", 0),
            tipo_cubierta=payload.get("tipo_cubierta", "pendiente_por_resolver"),
        )
        return {"mensaje": "Rectángulo creado correctamente.", "poligono": poligono}
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Falta el parámetro: {exc}",
        )
    except (TypeError, ValueError) as err:
        raise _http_error(ValueError(str(err)))


# ============================================================
# POLÍGONOS
# ============================================================


@modelos2d_router.patch("/{id}/poligonos/{id_poligono}")
def actualizar_poligono(
    id: int,
    id_poligono: str,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        return EditorModelo2DService.actualizar_poligono(
            db, id_modelo2d=id, id_poligono=id_poligono, datos=payload
        )
    except ValueError as err:
        raise _http_error(err)


@modelos2d_router.delete("/{id}/poligonos/{id_poligono}")
def eliminar_poligono(id: int, id_poligono: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    try:
        EditorModelo2DService.eliminar_poligono(db, id_modelo2d=id, id_poligono=id_poligono)
        return {"mensaje": "Superficie eliminada correctamente.", "id_poligono": id_poligono}
    except ValueError as err:
        raise _http_error(err)


# ------------------------------------------------------------
# VÉRTICES
# ------------------------------------------------------------


@modelos2d_router.post("/{id}/poligonos/{id_poligono}/vertices")
def agregar_vertice(
    id: int,
    id_poligono: str,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Body: { "punto": {"x": .., "y": ..}, "indice": opcional }"""
    try:
        if payload.get("punto") is None:
            raise ValueError("El campo 'punto' es obligatorio.")

        poligono = EditorModelo2DService.agregar_vertice_poligono(
            db,
            id_modelo2d=id,
            id_poligono=id_poligono,
            punto=payload["punto"],
            indice=payload.get("indice"),
        )
        return {"mensaje": "Vértice agregado correctamente.", "poligono": poligono}
    except ValueError as err:
        raise _http_error(err)


@modelos2d_router.delete("/{id}/poligonos/{id_poligono}/vertices/{indice}")
def eliminar_vertice(
    id: int, id_poligono: str, indice: int, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    try:
        poligono = EditorModelo2DService.eliminar_vertice_poligono(
            db, id_modelo2d=id, id_poligono=id_poligono, indice=indice
        )
        return {"mensaje": "Vértice eliminado correctamente.", "poligono": poligono}
    except ValueError as err:
        raise _http_error(err)


# ============================================================
# NIVELES
# ============================================================


@modelos2d_router.post("/{id}/niveles")
def crear_nivel(
    id: int, payload: Dict[str, Any] = Body(...), db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Body: { valor, texto?, punto_seleccionado: {x, y}, page?, capa?,
    id_poligono?, lado?, asociar_automaticamente? }"""
    try:
        if "valor" not in payload:
            raise ValueError("El campo 'valor' es obligatorio.")

        return EditorModelo2DService.crear_nivel(
            db,
            id_modelo2d=id,
            valor=payload["valor"],
            punto_seleccionado=payload.get("punto_seleccionado"),
            texto=payload.get("texto"),
            page=payload.get("page", 0),
            capa=payload.get("capa"),
            id_poligono=payload.get("id_poligono"),
            lado=payload.get("lado"),
            asociar_automaticamente=payload.get("asociar_automaticamente", True),
        )
    except ValueError as err:
        raise _http_error(err)


@modelos2d_router.patch("/{id}/niveles/{id_nivel}")
def actualizar_nivel(
    id: int,
    id_nivel: str,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        return EditorModelo2DService.actualizar_nivel(
            db, id_modelo2d=id, id_nivel=id_nivel, datos=payload
        )
    except ValueError as err:
        raise _http_error(err)


@modelos2d_router.delete("/{id}/niveles/{id_nivel}")
def eliminar_nivel(id: int, id_nivel: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    try:
        return EditorModelo2DService.eliminar_nivel(db, id_modelo2d=id, id_nivel=id_nivel)
    except ValueError as err:
        raise _http_error(err)


# ------------------------------------------------------------
# ASOCIAR / DESASOCIAR NIVEL <-> LADO DE POLÍGONO
# ------------------------------------------------------------


@modelos2d_router.post("/{id}/poligonos/{id_poligono}/niveles/{id_nivel}/asociar")
def asociar_nivel(
    id: int,
    id_poligono: str,
    id_nivel: str,
    payload: Optional[Dict[str, Any]] = Body(default=None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Body opcional: { "lado": int }. Sin "lado" se usa el lado más cercano."""
    try:
        modelo = EditorModelo2DService.asociar_nivel_poligono(
            db,
            id_modelo2d=id,
            id_poligono=id_poligono,
            id_nivel=id_nivel,
            lado=(payload or {}).get("lado"),
        )
        return {
            "mensaje": "Nivel asociado correctamente.",
            "poligono": _buscar_por_id(modelo.get("poligonos"), id_poligono),
            "nivel": _buscar_por_id(modelo.get("cotas_altura"), id_nivel),
        }
    except ValueError as err:
        raise _http_error(err)


@modelos2d_router.delete("/{id}/poligonos/{id_poligono}/niveles/{id_nivel}/desasociar")
def desasociar_nivel(
    id: int, id_poligono: str, id_nivel: str, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """El nivel no se borra: queda sin asociar y puede asociarse de nuevo."""
    try:
        modelo = EditorModelo2DService.desasociar_nivel_poligono(
            db, id_modelo2d=id, id_poligono=id_poligono, id_nivel=id_nivel
        )
        return {
            "mensaje": "Nivel desasociado correctamente.",
            "poligono": _buscar_por_id(modelo.get("poligonos"), id_poligono),
            "nivel": _buscar_por_id(modelo.get("cotas_altura"), id_nivel),
        }
    except ValueError as err:
        raise _http_error(err)


# ============================================================
# VALIDACIÓN
# ============================================================


@modelos2d_router.post("/{id}/validar")
def validar_modelo2d(id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Valida la geometría y marca el Modelo 2D como validado.

    "poligonos_sin_pendiente" es informativo (no bloquea).
    """
    try:
        EditorModelo2DService.validar_modelo2d(db, id_modelo2d=id)
        modelo = EditorModelo2DService.obtener_modelo2d(db, id)
    except ValueError as err:
        raise _http_error(err)

    poligonos = modelo.get("poligonos") or []
    return {
        "mensaje": "Modelo 2D validado y guardado correctamente.",
        "id_modelo2d": str(id),
        "validado": True,
        "cantidad_poligonos": len(poligonos),
        "cantidad_niveles": len(modelo.get("cotas_altura") or []),
        "poligonos_sin_pendiente": [
            p.get("id") for p in poligonos if not (p.get("pendiente") or {}).get("definida")
        ],
    }
