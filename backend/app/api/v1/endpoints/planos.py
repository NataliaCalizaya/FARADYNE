import os
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile, status
from app.core.config import settings
from app.repositories.plano_repository import PlanoRepository
from app.schemas.plano_schema import PlanoCreateResponse, PlanoPreviewResponse
from app.services.dxf_interpreter_service import DXFInterpreterService
from app.services.pdf_interpreter_service import PDFInterpreterService

router = APIRouter(prefix="/planos", tags=["HU02 - Planos"])
modelos2d_router = APIRouter(prefix="/modelos2d", tags=["HU02 - Modelo 2D"])


@router.post("", response_model=PlanoCreateResponse, status_code=status.HTTP_201_CREATED)
async def upload_plano(
    file: UploadFile = File(...),
    idProyecto: str = Form(..., description="ID del proyecto asociado"),
) -> Dict[str, Any]:
    """HU02: Upload architectural drawing (DXF or PDF) for project."""
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

    # Saved file path
    unique_filename = f"{uuid.uuid4().hex}_{filename}"
    saved_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    parsed_data = {}
    capas = []
    poligonos = []
    cotas_altura = []
    lineas = []

    if ext == ".dxf":
        # Validate DXF parseability using ezdxf
        try:
            doc = DXFInterpreterService.validate_and_read_dxf(file_bytes, filename)
            parsed_data = DXFInterpreterService.interpret_dxf_data(doc)
            capas = parsed_data.get("capas", [])
            poligonos = parsed_data.get("poligonos", [])
            cotas_altura = parsed_data.get("cotas_altura", [])
            lineas = parsed_data.get("lineas", [])
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(err),
            )
    elif ext == ".pdf":
        # Validate PDF vector parseability using PyMuPDF (fitz)
        try:
            doc = PDFInterpreterService.validate_and_read_pdf(file_bytes, filename)
            parsed_data = PDFInterpreterService.interpret_pdf_data(doc, file_bytes=file_bytes)
            capas = parsed_data.get("capas", [])
            poligonos = parsed_data.get("poligonos", [])
            cotas_altura = parsed_data.get("cotas_altura", [])
            lineas = parsed_data.get("lineas", [])

        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(err),
            )

    # Save file to disk
    try:
        with open(saved_path, "wb") as f:
            f.write(file_bytes)
    except Exception as io_err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al guardar el archivo en el servidor: {io_err}",
        )

    # Save DB record in table 'plano'
    plano_db = PlanoRepository.create_plano(
        id_proyecto=idProyecto,
        nombre_archivo=filename,
        tipo_archivo=ext.replace(".", "").upper(),
        ruta_archivo=saved_path,
        tamano_bytes=tamano_bytes,
        metadatos={"bounding_box": parsed_data.get("bounding_box", {})},
    )

    id_plano = str(plano_db.get("id_plano", plano_db.get("id", "")))

    # Create associated modelo2d entry (without entidades_geom)
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
        "fecha_creacion": plano_db.get("fecha_carga") or plano_db.get("fecha_creacion"),
        "id_modelo2d": id_modelo2d,
    }


@router.get("/{id}/preview", response_model=PlanoPreviewResponse)
def get_plano_preview(id: str) -> Dict[str, Any]:
    """HU02: Get preview data for interpreted drawing."""
    plano = PlanoRepository.get_plano_by_id(id)
    if not plano:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el plano con ID '{id}'.",
        )

    modelo2d = PlanoRepository.get_modelo2d_by_plano_id(id)
    id_plano_str = str(plano.get("id_plano", plano.get("id", id)))

    metadatos = plano.get("metadatos", {}) if plano else {}
    bounding_box = metadatos.get("bounding_box", {})

    return {
        "id": id_plano_str,
        "id_proyecto": str(plano.get("id_proyecto", "")),
        "nombre_archivo": plano.get("nombre_archivo", ""),
        "tipo_archivo": plano.get("tipo_archivo", ""),
        "ruta_archivo": plano.get("ruta_archivo", ""),
        "bounding_box": bounding_box,
        "capas": modelo2d.get("capas", []) if modelo2d else [],
        "cotas_altura": modelo2d.get("cotas_altura", []) if modelo2d else [],
        "poligonos": modelo2d.get("poligonos", []) if modelo2d else [],
        "lineas": modelo2d.get("lineas", []) if modelo2d else [],
    }



@modelos2d_router.patch("/{id}")
def update_modelo2d_endpoint(
    id: str,
    payload: Dict[str, Any] = Body(...),
) -> Dict[str, Any]:
    """HU02: Update corrected 2D model geometry (poligonos, lineas, capas, validado)."""
    modelo2d = PlanoRepository.get_modelo2d_by_id(id)
    if not modelo2d:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el Modelo 2D con ID '{id}'.",
        )

    poligonos = payload.get("poligonos")
    lineas = payload.get("lineas")
    capas = payload.get("capas")
    cotas_altura = payload.get("cotas_altura")
    validado = payload.get("validado")

    updated = PlanoRepository.update_modelo2d(
        id_modelo2d=id,
        poligonos=poligonos,
        lineas=lineas,
        capas=capas,
        cotas_altura=cotas_altura,
        validado=validado,
    )

    if not updated:
        updated = modelo2d

    return {
        "id": str(updated.get("id_modelo2d", id)),
        "id_plano": str(updated.get("id_plano", "")),
        "validado": bool(updated.get("validado", False)),
        "poligonos": updated.get("poligonos", []),
        "lineas": updated.get("lineas", []),
        "capas": updated.get("capas", []),
        "cotas_altura": updated.get("cotas_altura", []),
        "mensaje": "Modelo 2D actualizado correctamente.",
    }


