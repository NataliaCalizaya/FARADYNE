from typing import Any, Dict, List, Optional
from app.core.database import execute_query, fetch_all, fetch_one


class MastilRepository:

    @staticmethod
    def create_mastil(
        id_modelo3d: str,
        id_proyecto: Optional[str] = None,
        posicion_x: float = 0.0,
        posicion_y: float = 0.0,
        posicion_z: float = 0.0,
        altura: float = 0.0,
        tipo: str = "Franklin",
        radio_cobertura: Optional[float] = None,
        angulo_proteccion: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Save a new air terminal mast entry in table 'mastil'."""
        query = """
            INSERT INTO mastil (id_modelo3d, coordenada_x, coordenada_y, altura, tipo)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *;
        """
        params = (
            id_modelo3d,
            posicion_x,
            posicion_y,
            altura,
            tipo,
        )
        res = execute_query(query, params, fetch=True)
        return res[0] if isinstance(res, list) and res else (res if res else {})

    @staticmethod
    def update_mastil(
        id_mastil: str,
        posicion_x: Optional[float] = None,
        posicion_y: Optional[float] = None,
        posicion_z: Optional[float] = None,
        altura: Optional[float] = None,
        tipo: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update coordinates, height or type of mast."""
        fields = []
        params = []

        if posicion_x is not None:
            fields.append("coordenada_x = %s")
            params.append(posicion_x)
        if posicion_y is not None:
            fields.append("coordenada_y = %s")
            params.append(posicion_y)
        if altura is not None:
            fields.append("altura = %s")
            params.append(altura)
        if tipo is not None:
            fields.append("tipo = %s")
            params.append(tipo)

        if not fields:
            return MastilRepository.get_mastil_by_id(id_mastil)

        params.append(id_mastil)
        query = f"UPDATE mastil SET {', '.join(fields)} WHERE id_mastil = %s RETURNING *;"
        res = execute_query(query, tuple(params), fetch=True)
        return res[0] if isinstance(res, list) and res else (res if res else None)

    @staticmethod
    def delete_mastil(id_mastil: str) -> bool:
        """Delete mast entry by primary key id_mastil."""
        query = "DELETE FROM mastil WHERE id_mastil = %s RETURNING id_mastil;"
        res = execute_query(query, (id_mastil,), fetch=True)
        return res is not None

    @staticmethod
    def get_mastil_by_id(id_mastil: str) -> Optional[Dict[str, Any]]:
        """Fetch mast record by primary key id_mastil."""
        query = "SELECT * FROM mastil WHERE id_mastil = %s;"
        return fetch_one(query, (id_mastil,))

    @staticmethod
    def get_mastiles_by_proyecto_id(id_proyecto: str) -> List[Dict[str, Any]]:
        """Fetch all mast entries associated with a project through modelo3d, modelo2d and plano."""
        query = """
            SELECT m.*
            FROM mastil m
            JOIN modelo3d m3d ON m.id_modelo3d = m3d.id_modelo3d
            JOIN modelo2d m2d ON m3d.id_modelo2d = m2d.id_modelo2d
            JOIN plano p ON m2d.id_plano = p.id_plano
            WHERE p.id_proyecto = %s
            ORDER BY m.id_mastil ASC;
        """
        res = fetch_all(query, (id_proyecto,))
        return res if res else []

    @staticmethod
    def get_mastiles_by_modelo3d_id(id_modelo3d: str) -> List[Dict[str, Any]]:
        """Fetch all mast entries associated with a 3D model."""
        query = "SELECT * FROM mastil WHERE id_modelo3d = %s ORDER BY id_mastil ASC;"
        res = fetch_all(query, (id_modelo3d,))
        return res if res else []

