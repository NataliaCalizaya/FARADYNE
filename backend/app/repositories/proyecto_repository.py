from typing import Any, Dict, Optional
from app.core.database import fetch_one


class ProyectoRepository:

    @staticmethod
    def get_proyecto_by_id(id_proyecto: str) -> Optional[Dict[str, Any]]:
        """Fetch de la fila completa de 'proyecto' por id_proyecto."""
        query = "SELECT * FROM proyecto WHERE id_proyecto = %s;"
        return fetch_one(query, (id_proyecto,))

    @staticmethod
    def get_ubicacion_by_proyecto_id(id_proyecto: str) -> Optional[Dict[str, Any]]:
        """Trae solo id/nombre/ubicacion del proyecto.

        Se usa para mostrar la ubicación junto al Ng adoptado en el Paso 1
        del cálculo de Nivel de Protección (HU04), sin traer la fila entera.
        """
        query = """
            SELECT id_proyecto, nombre, ubicacion
            FROM proyecto
            WHERE id_proyecto = %s;
        """
        return fetch_one(query, (id_proyecto,))