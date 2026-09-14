from typing import Any, Dict, Optional
from app.core.database import execute_query, fetch_one, serialize_json


class Modelo3DRepository:

    @staticmethod
    def create_modelo3d(
        id_modelo2d: str,
        id_proyecto: Optional[str] = None,
        geometria_volumetrica: Optional[Dict[str, Any]] = None,
        vista_defecto: Optional[Dict[str, Any]] = None,
        escala: float = 1.0,
        altura_h: float = 0.0,
    ) -> Dict[str, Any]:
        """Save generated 3D volumetric mesh in table 'modelo3d' using parameterized SQL."""
        if geometria_volumetrica is None:
            geometria_volumetrica = {}

        query = """
            INSERT INTO modelo3d (id_modelo2d, geometria_volumetrica, escala, fecha_generacion, altura_h)
            VALUES (%s, %s::jsonb, %s, CURRENT_DATE, %s)
            RETURNING *;
        """
        params = (
            id_modelo2d,
            serialize_json(geometria_volumetrica),
            escala,
            altura_h,
        )
        res = execute_query(query, params, fetch=True)
        return res[0] if isinstance(res, list) and res else (res if res else {})

    @staticmethod
    def get_modelo3d_by_id(id_modelo3d: str) -> Optional[Dict[str, Any]]:
        """Fetch 3D model by primary key id_modelo3d."""
        query = "SELECT * FROM modelo3d WHERE id_modelo3d = %s;"
        return fetch_one(query, (id_modelo3d,))

    @staticmethod
    def get_modelo3d_by_proyecto_id(id_proyecto: str) -> Optional[Dict[str, Any]]:
        """Fetch most recent 3D model associated with project id through modelo2d and plano."""
        query = """
            SELECT m3d.*
            FROM modelo3d m3d
            JOIN modelo2d m2d ON m3d.id_modelo2d = m2d.id_modelo2d
            JOIN plano p ON m2d.id_plano = p.id_plano
            WHERE p.id_proyecto = %s
            ORDER BY m3d.id_modelo3d DESC
            LIMIT 1;
        """
        return fetch_one(query, (id_proyecto,))

    @staticmethod
    def update_vista_defecto(id_modelo3d: str, vista_defecto: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Fetch model by primary key id_modelo3d for camera reset view."""
        return Modelo3DRepository.get_modelo3d_by_id(id_modelo3d)

