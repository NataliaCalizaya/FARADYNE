from typing import Any, Dict, List, Optional
from app.core.database import execute_query, fetch_all, fetch_one


def _map_mastil_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza una fila de la tabla 'mastil' al contrato del schema MastilResponse.
    
    La tabla usa:
      - id (PK UUID)
      - posicion_x, posicion_y
      - id_modelo3d, id_proyecto
    """
    if not row:
        return row
    return {
        "id": str(row.get("id_mastil", "")),
        "id_modelo2d": str(row.get("id_modelo2d", "")),
        "id_proyecto": str(row.get("id_proyecto", "")) if row.get("id_proyecto") else None,
        "posicion_x": float(row.get("posicion_x", 0.0)),
        "posicion_y": float(row.get("posicion_y", 0.0)),
        "posicion_z": float(row.get("posicion_z", 0.0)),
        "altura": float(row.get("altura", 0.0)),
        "tipo": str(row.get("tipo", "Franklin")),
        "radio_cobertura": row.get("radio_cobertura"),
        "fecha_creacion": row.get("fecha_creacion"),
    }


class MastilRepository:

    @staticmethod
    def create_mastil(
        id_modelo2d: str,
        id_proyecto: Optional[str] = None,
        posicion_x: float = 0.0,
        posicion_y: float = 0.0,
        posicion_z: float = 0.0,
        altura: float = 0.0,
        tipo: str = "Franklin",
        radio_cobertura: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Persiste un nuevo mástil captor en la tabla 'mastil'."""
        # The table no longer contains the column `id_proyecto`. We therefore omit it from the INSERT statement.
        query = """
            INSERT INTO mastil (id_modelo2d, posicion_x, posicion_y, posicion_z, altura, tipo, radio_cobertura)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *;
        """
        params = (
            id_modelo2d,
            posicion_x,
            posicion_y,
            posicion_z,
            altura,
            tipo,
            radio_cobertura,
        )
        res = execute_query(query, params, fetch=True)
        raw = res[0] if isinstance(res, list) and res else (res if res else {})
        return _map_mastil_row(raw)

    @staticmethod
    def update_mastil(
        id_mastil: str,
        posicion_x: Optional[float] = None,
        posicion_y: Optional[float] = None,
        posicion_z: Optional[float] = None,
        altura: Optional[float] = None,
        tipo: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Actualiza coordenadas, altura o tipo del mástil."""
        fields = []
        params = []

        if posicion_x is not None:
            fields.append("posicion_x = %s")
            params.append(posicion_x)
        if posicion_y is not None:
            fields.append("posicion_y = %s")
            params.append(posicion_y)
        if posicion_z is not None:
            fields.append("posicion_z = %s")
            params.append(posicion_z)
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
        raw = res[0] if isinstance(res, list) and res else (res if res else None)
        return _map_mastil_row(raw) if raw else None

    @staticmethod
    def delete_mastil(id_mastil: str) -> bool:
        """Elimina un mástil por clave primaria."""
        query = "DELETE FROM mastil WHERE id_mastil = %s RETURNING id_mastil;"
        res = execute_query(query, (id_mastil,), fetch=True)
        return res is not None

    @staticmethod
    def get_mastil_by_id(id_mastil: str) -> Optional[Dict[str, Any]]:
        """Obtiene un mástil por clave primaria."""
        query = "SELECT * FROM mastil WHERE id_mastil = %s;"
        raw = fetch_one(query, (id_mastil,))
        return _map_mastil_row(raw) if raw else None

    @staticmethod
    def get_mastiles_by_proyecto_id(id_proyecto: str) -> List[Dict[str, Any]]:
        """Obtiene todos los mástiles de un proyecto, vía modelo2d → plano → proyecto
        (la tabla 'mastil' no tiene id_proyecto directo, solo id_modelo2d)."""
        query = """
            SELECT m.*
            FROM mastil m
            JOIN modelo2d m2d ON m.id_modelo2d = m2d.id_modelo2d
            JOIN plano p ON m2d.id_plano = p.id_plano
            WHERE p.id_proyecto = %s
            ORDER BY m.fecha_creacion ASC;
        """
        res = fetch_all(query, (id_proyecto,))
        return [_map_mastil_row(r) for r in res] if res else []

    @staticmethod
    def get_mastiles_by_modelo3d_id(id_modelo3d: str) -> List[Dict[str, Any]]:
        """Obtiene todos los mástiles asociados a un modelo 3D mediante modelo2d."""
        query = """
            SELECT m.*
            FROM mastil m
            JOIN modelo3d m3d ON m.id_modelo2d = m3d.id_modelo2d
            WHERE m3d.id_modelo3d = %s
            ORDER BY m.fecha_creacion ASC;
        """
        res = fetch_all(query, (id_modelo3d,))
        return [_map_mastil_row(r) for r in res] if res else []

    @staticmethod
    def get_mastiles_by_modelo2d_id(id_modelo2d: str) -> List[Dict[str, Any]]:
        """Obtiene los mástiles asociados directamente a un modelo 2D mediante la FK id_modelo2d."""
        query = "SELECT * FROM mastil WHERE id_modelo2d = %s ORDER BY fecha_creacion ASC;"
        res = fetch_all(query, (id_modelo2d,))
        return [_map_mastil_row(r) for r in res] if res else []
