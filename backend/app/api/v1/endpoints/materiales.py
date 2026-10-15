from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.mastil_repository import MastilRepository
from app.repositories.material_repository import MaterialRepository
from app.schemas.material_schema import ListadoMaterialesResponse
from app.services.material_list_service import calcular_listado_materiales

router = APIRouter(prefix="/materiales", tags=["Listado de Materiales"])


@router.get("/proyecto/{id_proyecto}", response_model=ListadoMaterialesResponse)
def get_listado_materiales(id_proyecto: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Cómputo de materiales de un proyecto según los mástiles guardados.
    Sin mástiles -> lista de ítems vacía."""
    mastiles = MastilRepository.get_mastiles_by_proyecto_id(db, id_proyecto)
    catalogo = MaterialRepository.get_codigos(db)
    return {
        "id_proyecto": str(id_proyecto),
        "total_mastiles": len(mastiles),
        "items": calcular_listado_materiales(mastiles, catalogo),
    }