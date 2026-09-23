import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Body,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)

from app.core.config import settings
from app.repositories.plano_repository import PlanoRepository
from app.schemas.plano_schema import (
    PlanoCreateResponse,
    PlanoPreviewResponse,
)
from app.services.dxf_interpreter_service import DXFInterpreterService
from app.services.editor_modelo2d_service import EditorModelo2DService
from app.services.niveles_utils import NivelesUtils
from app.services.pdf_interpreter_service import PDFInterpreterService


router = APIRouter(
    prefix="/planos",
    tags=["HU02 - Planos"],
)

modelos2d_router = APIRouter(
    prefix="/modelos2d",
    tags=["HU02 - Modelo 2D"],
)


# ============================================================
# UTILIDADES
# ============================================================


def _http_error(err: ValueError) -> HTTPException:
    """
    El servicio del editor informa todo con ValueError. Si el elemento no
    existe respondemos 404 (el visor lo usa para resincronizarse); cualquier
    otra validación es un 400.
    """
    detalle = str(err)

    codigo = (
        status.HTTP_404_NOT_FOUND
        if detalle.startswith("No se encontró")
        else status.HTTP_400_BAD_REQUEST
    )

    return HTTPException(status_code=codigo, detail=detalle)


def _buscar_por_id(
    items: Optional[List[Dict[str, Any]]],
    item_id: str,
) -> Optional[Dict[str, Any]]:
    return next(
        (i for i in (items or []) if str(i.get("id")) == str(item_id)),
        None,
    )


# ============================================================
# PLANOS
# ============================================================


@router.post(
    "",
    response_model=PlanoCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_plano(
    file: UploadFile = File(...),
    idProyecto: str = Form(
        ...,
        description="ID del proyecto asociado",
    ),
) -> Dict[str, Any]:
    """
    HU02: carga e interpretación de un plano DXF o PDF.

        archivo -> intérprete -> Modelo 2D -> persistencia

    El intérprete de PDF ya devuelve los niveles asociados a un lado de un
    polígono (cotas_altura[i]["asociaciones"]); los que no tenían polígono
    cerca se descartan y no llegan acá.
    """
    filename = file.filename or "plano_sin_nombre"
    ext = os.path.splitext(filename)[1].lower()

    if ext not in (".dxf", ".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Formato no soportado '{ext}'. "
                "Solo se admiten archivos .dxf y .pdf."
            ),
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

    # --------------------------------------------------------
    # INTERPRETACIÓN
    # --------------------------------------------------------

    try:
        if ext == ".dxf":
            doc = DXFInterpreterService.validate_and_read_dxf(
                file_bytes,
                filename,
            )
            parsed_data = DXFInterpreterService.interpret_dxf_data(doc)

        else:
            doc = PDFInterpreterService.validate_and_read_pdf(
                file_bytes,
                filename,
            )
            parsed_data = PDFInterpreterService.interpret_pdf_data(
                doc,
                file_bytes=file_bytes,
            )

    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        )

    capas = parsed_data.get("capas", [])
    poligonos = parsed_data.get("poligonos", [])
    cotas_altura = parsed_data.get("cotas_altura", [])
    lineas = parsed_data.get("lineas", [])

    # --------------------------------------------------------
    # GUARDAR ARCHIVO
    # --------------------------------------------------------

    try:
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

        with open(saved_path, "wb") as f:
            f.write(file_bytes)

    except Exception as io_err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al guardar el archivo en el servidor: {io_err}",
        )

    # --------------------------------------------------------
    # GUARDAR PLANO
    # --------------------------------------------------------

    plano_db = PlanoRepository.create_plano(
        id_proyecto=idProyecto,
        nombre_archivo=filename,
        tipo_archivo=ext.replace(".", "").upper(),
        ruta_archivo=saved_path,
        tamano_bytes=tamano_bytes,
        metadatos={
            "bounding_box": parsed_data.get("bounding_box", {}),
        },
    )

    id_plano = str(plano_db.get("id_plano", plano_db.get("id", "")))

    # --------------------------------------------------------
    # CREAR MODELO 2D
    # --------------------------------------------------------

    modelo2d_db = PlanoRepository.create_modelo2d(
        id_plano=id_plano,
        id_proyecto=idProyecto,
        poligonos=poligonos,
        capas=capas,
        cotas_altura=cotas_altura,
        lineas=lineas,
    )

    id_modelo2d = str(modelo2d_db.get("id_modelo2d", modelo2d_db.get("id", "")))

    return {
        "id": id_plano,
        "id_proyecto": idProyecto,
        "nombre_archivo": filename,
        "tipo_archivo": ext.replace(".", ""),
        "ruta_archivo": saved_path,
        "tamano_bytes": tamano_bytes,
        "metadatos": plano_db.get("metadatos", {}),
        "fecha_creacion": (
            plano_db.get("fecha_carga") or plano_db.get("fecha_creacion")
        ),
        "id_modelo2d": id_modelo2d,
    }


# ============================================================
# PREVIEW DEL PLANO
# ============================================================


@router.get(
    "/{id}/preview",
    response_model=PlanoPreviewResponse,
)
def get_plano_preview(id: str) -> Dict[str, Any]:
    """
    Todo lo que necesita el visor para dibujar el plano: líneas, capas,
    polígonos y niveles (con sus asociaciones a lados de polígono).
    """
    plano = PlanoRepository.get_plano_by_id(id)

    if not plano:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el plano con ID '{id}'.",
        )

    modelo2d = PlanoRepository.get_modelo2d_by_plano_id(id) or {}

    poligonos = modelo2d.get("poligonos") or []
    cotas_altura = modelo2d.get("cotas_altura") or []

    # Modelos guardados antes de las asociaciones por lado: se migran en
    # memoria; el primer guardado del editor los persiste con el formato nuevo.
    NivelesUtils.migrar_formato_anterior(poligonos, cotas_altura)

    metadatos = plano.get("metadatos") or {}

    id_modelo2d = modelo2d.get("id_modelo2d", modelo2d.get("id"))

    return {
        "id": str(plano.get("id_plano", plano.get("id", id))),
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
# MODELO 2D - OBTENER
# ============================================================


@modelos2d_router.get("/{id}")
def get_modelo2d(id: str) -> Dict[str, Any]:
    try:
        return EditorModelo2DService.obtener_modelo2d(id)

    except ValueError as err:
        raise _http_error(err)


@modelos2d_router.get("/{id}/edicion")
def get_modelo2d_edicion(id: str) -> Dict[str, Any]:
    """
    Estado editable del Modelo 2D (sin las líneas de fondo, que son pesadas).
    El visor lo pide después de cada operación para mostrar siempre lo que
    quedó guardado en el servidor.
    """
    try:
        modelo = EditorModelo2DService.obtener_modelo2d(id)

    except ValueError as err:
        raise _http_error(err)

    return {
        "id_modelo2d": id,
        "validado": bool(modelo.get("validado", False)),
        "capas": modelo.get("capas") or [],
        "poligonos": modelo.get("poligonos") or [],
        "cotas_altura": modelo.get("cotas_altura") or [],
    }


# ============================================================
# MODELO 2D - ACTUALIZACIÓN GENERAL
# ============================================================


@modelos2d_router.patch("/{id}")
def update_modelo2d_endpoint(
    id: str,
    payload: Dict[str, Any] = Body(...),
) -> Dict[str, Any]:
    """
    Actualización general del Modelo2D (compatibilidad). Para editar usar
    los endpoints específicos de polígonos, vértices, niveles y validación.
    """
    modelo = PlanoRepository.get_modelo2d_by_id(id)

    if not modelo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el Modelo 2D con ID '{id}'.",
        )

    updated = PlanoRepository.update_modelo2d(
        id_modelo2d=id,
        poligonos=payload.get("poligonos"),
        lineas=payload.get("lineas"),
        capas=payload.get("capas"),
        cotas_altura=payload.get("cotas_altura"),
        colores=payload.get("colores"),
        validado=payload.get("validado"),
    )

    if not updated:
        updated = modelo

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
# SUPERFICIES NUEVAS (se crean distinto, después son polígonos)
# ============================================================


@modelos2d_router.post("/{id}/triangulos")
def create_triangulo(
    id: str,
    payload: Dict[str, Any] = Body(...),
) -> Dict[str, Any]:
    try:
        if "puntos" not in payload:
            raise ValueError("El campo 'puntos' es obligatorio.")

        poligono = EditorModelo2DService.crear_triangulo(
            id_modelo2d=id,
            puntos=payload["puntos"],
            capa=payload.get("capa"),
            page=payload.get("page", 0),
            tipo_cubierta=payload.get("tipo_cubierta", "pendiente_por_resolver"),
        )

        return {
            "mensaje": "Triángulo creado correctamente.",
            "poligono": poligono,
        }

    except ValueError as err:
        raise _http_error(err)


@modelos2d_router.post("/{id}/rectangulos")
def create_rectangulo(
    id: str,
    payload: Dict[str, Any] = Body(...),
) -> Dict[str, Any]:
    try:
        poligono = EditorModelo2DService.crear_rectangulo(
            id_modelo2d=id,
            x1=float(payload["x1"]),
            y1=float(payload["y1"]),
            x2=float(payload["x2"]),
            y2=float(payload["y2"]),
            capa=payload.get("capa"),
            page=payload.get("page", 0),
            tipo_cubierta=payload.get("tipo_cubierta", "pendiente_por_resolver"),
        )

        return {
            "mensaje": "Rectángulo creado correctamente.",
            "poligono": poligono,
        }

    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Falta el parámetro: {exc}",
        )

    except (TypeError, ValueError) as err:
        raise _http_error(ValueError(str(err)))


# ============================================================
# POLÍGONOS (edición y borrado son iguales para todos)
# ============================================================


@modelos2d_router.patch("/{id}/poligonos/{id_poligono}")
def actualizar_poligono(
    id: str,
    id_poligono: str,
    payload: Dict[str, Any] = Body(...),
) -> Dict[str, Any]:
    try:
        return EditorModelo2DService.actualizar_poligono(
            id_modelo2d=id,
            id_poligono=id_poligono,
            datos=payload,
        )

    except ValueError as err:
        raise _http_error(err)


@modelos2d_router.delete("/{id}/poligonos/{id_poligono}")
def eliminar_poligono(id: str, id_poligono: str) -> Dict[str, Any]:
    try:
        EditorModelo2DService.eliminar_poligono(
            id_modelo2d=id,
            id_poligono=id_poligono,
        )

        return {
            "mensaje": "Superficie eliminada correctamente.",
            "id_poligono": id_poligono,
        }

    except ValueError as err:
        raise _http_error(err)


# ------------------------------------------------------------
# VÉRTICES
# ------------------------------------------------------------


@modelos2d_router.post("/{id}/poligonos/{id_poligono}/vertices")
def agregar_vertice(
    id: str,
    id_poligono: str,
    payload: Dict[str, Any] = Body(...),
) -> Dict[str, Any]:
    """
    Body: { "punto": {"x": .., "y": ..}, "indice": opcional }

    Sin "indice" el vértice se inserta sobre el lado más cercano al punto.
    """
    try:
        if payload.get("punto") is None:
            raise ValueError("El campo 'punto' es obligatorio.")

        poligono = EditorModelo2DService.agregar_vertice_poligono(
            id_modelo2d=id,
            id_poligono=id_poligono,
            punto=payload["punto"],
            indice=payload.get("indice"),
        )

        return {
            "mensaje": "Vértice agregado correctamente.",
            "poligono": poligono,
        }

    except ValueError as err:
        raise _http_error(err)


@modelos2d_router.delete("/{id}/poligonos/{id_poligono}/vertices/{indice}")
def eliminar_vertice(
    id: str,
    id_poligono: str,
    indice: int,
) -> Dict[str, Any]:
    try:
        poligono = EditorModelo2DService.eliminar_vertice_poligono(
            id_modelo2d=id,
            id_poligono=id_poligono,
            indice=indice,
        )

        return {
            "mensaje": "Vértice eliminado correctamente.",
            "poligono": poligono,
        }

    except ValueError as err:
        raise _http_error(err)


# ============================================================
# NIVELES
# ============================================================


@modelos2d_router.post("/{id}/niveles")
def crear_nivel(
    id: str,
    payload: Dict[str, Any] = Body(...),
) -> Dict[str, Any]:
    """
    Body: { valor, texto?, punto_seleccionado: {x, y}, page?, capa?,
            id_poligono?, lado?, asociar_automaticamente? }

    Devuelve { mensaje, nivel }. Si no hay polígono cerca el nivel queda
    creado con "asociado": false y se puede asociar después.
    """
    try:
        if "valor" not in payload:
            raise ValueError("El campo 'valor' es obligatorio.")

        return EditorModelo2DService.crear_nivel(
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
    id: str,
    id_nivel: str,
    payload: Dict[str, Any] = Body(...),
) -> Dict[str, Any]:
    try:
        return EditorModelo2DService.actualizar_nivel(
            id_modelo2d=id,
            id_nivel=id_nivel,
            datos=payload,
        )

    except ValueError as err:
        raise _http_error(err)


@modelos2d_router.delete("/{id}/niveles/{id_nivel}")
def eliminar_nivel(id: str, id_nivel: str) -> Dict[str, Any]:
    try:
        return EditorModelo2DService.eliminar_nivel(
            id_modelo2d=id,
            id_nivel=id_nivel,
        )

    except ValueError as err:
        raise _http_error(err)


# ------------------------------------------------------------
# ASOCIAR / DESASOCIAR NIVEL <-> LADO DE POLÍGONO
# ------------------------------------------------------------


@modelos2d_router.post(
    "/{id}/poligonos/{id_poligono}/niveles/{id_nivel}/asociar"
)
def asociar_nivel(
    id: str,
    id_poligono: str,
    id_nivel: str,
    payload: Optional[Dict[str, Any]] = Body(default=None),
) -> Dict[str, Any]:
    """
    Body opcional: { "lado": int }. Sin "lado" se usa el lado más cercano al
    nivel. Sirve para niveles reconocidos y para niveles creados a mano.
    """
    try:
        modelo = EditorModelo2DService.asociar_nivel_poligono(
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


@modelos2d_router.delete(
    "/{id}/poligonos/{id_poligono}/niveles/{id_nivel}/desasociar"
)
def desasociar_nivel(
    id: str,
    id_poligono: str,
    id_nivel: str,
) -> Dict[str, Any]:
    """El nivel no se borra: queda sin asociar y puede asociarse de nuevo."""
    try:
        modelo = EditorModelo2DService.desasociar_nivel_poligono(
            id_modelo2d=id,
            id_poligono=id_poligono,
            id_nivel=id_nivel,
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
def validar_modelo2d(id: str) -> Dict[str, Any]:
    """
    Valida la geometría y marca el Modelo 2D como validado. Cualquier edición
    posterior lo vuelve a dejar sin validar.

    "poligonos_sin_pendiente" es informativo (no bloquea): superficies que
    todavía no tienen dos niveles en lados distintos.
    """
    try:
        EditorModelo2DService.validar_modelo2d(id_modelo2d=id)

    except ValueError as err:
        raise _http_error(err)

    modelo = EditorModelo2DService.obtener_modelo2d(id)
    poligonos = modelo.get("poligonos") or []

    return {
        "mensaje": "Modelo 2D validado y guardado correctamente.",
        "id_modelo2d": id,
        "validado": True,
        "cantidad_poligonos": len(poligonos),
        "cantidad_niveles": len(modelo.get("cotas_altura") or []),
        "poligonos_sin_pendiente": [
            p.get("id")
            for p in poligonos
            if not (p.get("pendiente") or {}).get("definida")
        ],
    }
