from typing import Any, Dict, List, Optional
from app.core.database import execute_query, fetch_all, fetch_one, serialize_json


class PlanoRepository:

    @staticmethod
    def get_proyecto_by_id(id_proyecto: str) -> Optional[Dict[str, Any]]:
        """Get project by ID, create dummy if it doesn't exist to satisfy FK constraints in dev."""
        query = "SELECT * FROM proyecto WHERE id_proyecto = %s;"
        row = fetch_one(query, (id_proyecto,))
        if not row:
            # Auto-insert default project if needed
            insert_query = """
                INSERT INTO proyecto (nombre, cliente, ubicacion, fecha_creacion)
                VALUES (%s, %s, %s, CURRENT_DATE)
                RETURNING *;
            """
            row = execute_query(
                insert_query,
                (f"Proyecto {str(id_proyecto)[:8]}", "Cliente General", "Ubicación General"),
                fetch=True,
            )
            if isinstance(row, list) and row:
                row = row[0]
        return row

    @staticmethod
    def create_plano(
        id_proyecto: str,
        nombre_archivo: str,
        tipo_archivo: str,
        ruta_archivo: str,
        tamano_bytes: int = 0,
        metadatos: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Save plano metadata in table 'plano' using parameterized SQL."""
        query = """
            INSERT INTO plano (id_proyecto, nombre_archivo, tipo_archivo, ruta_archivo, fecha_carga, tamano_bytes, metadatos)
            VALUES (%s, %s, %s, %s, CURRENT_DATE, %s, %s::jsonb)
         
            RETURNING *;
        """
        params = (
            id_proyecto,
            nombre_archivo,
            tipo_archivo,
            ruta_archivo,
            tamano_bytes,
            serialize_json(metadatos or {}),
        )
        resultado = execute_query(query, params, fetch=True)
        return resultado if resultado else {}

    @staticmethod
    def create_modelo2d(
        id_plano: str,
        id_proyecto: Optional[str] = None,
        poligonos: Optional[List[Dict[str, Any]]] = None,
        capas: Optional[List[Dict[str, Any]]] = None,
        cotas_altura: Optional[List[Dict[str, Any]]] = None,
        lineas: Optional[List[Dict[str, Any]]] = None,
        colores: Optional[List[Dict[str, Any]]] = None,
        validado: bool = False,
    ) -> Dict[str, Any]:
        """Save parsed 2D model data in table 'modelo2d' using parameterized SQL."""
        if poligonos is None:
            poligonos = []
        if capas is None:
            capas = []
        if cotas_altura is None:
            cotas_altura = []
        if lineas is None:
            lineas = []
        if colores is None:
            colores = []

        query = """
            INSERT INTO modelo2d (id_plano, poligonos, lineas, capas, colores, cotas_altura, validado)
            VALUES (%s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s)
            RETURNING *;
        """
        params = (
            id_plano,
            serialize_json(poligonos),
            serialize_json(lineas),
            serialize_json(capas),
            serialize_json(colores),
            serialize_json(cotas_altura),
            validado,
        )
        resultado = execute_query(query, params, fetch=True)
        return resultado if resultado else {}

    @staticmethod
    def update_modelo2d(
        id_modelo2d: str,
        poligonos: Optional[List[Dict[str, Any]]] = None,
        lineas: Optional[List[Dict[str, Any]]] = None,
        capas: Optional[List[Dict[str, Any]]] = None,
        cotas_altura: Optional[List[Dict[str, Any]]] = None,
        colores: Optional[List[Dict[str, Any]]] = None,
        validado: Optional[bool] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update corrected 2D model geometry and validation status in table 'modelo2d'."""
        fields = []
        params = []

        if poligonos is not None:
            fields.append("poligonos = %s::jsonb")
            params.append(serialize_json(poligonos))
        if lineas is not None:
            fields.append("lineas = %s::jsonb")
            params.append(serialize_json(lineas))
        if capas is not None:
            fields.append("capas = %s::jsonb")
            params.append(serialize_json(capas))
        if cotas_altura is not None:
            fields.append("cotas_altura = %s::jsonb")
            params.append(serialize_json(cotas_altura))
        if colores is not None:
            fields.append("colores = %s::jsonb")
            params.append(serialize_json(colores))
        if validado is not None:
            fields.append("validado = %s")
            params.append(validado)

        if not fields:
            return PlanoRepository.get_modelo2d_by_id(id_modelo2d)

        params.append(id_modelo2d)
        query = f"UPDATE modelo2d SET {', '.join(fields)} WHERE id_modelo2d = %s RETURNING *;"
        res = execute_query(query, tuple(params), fetch=True)
        if isinstance(res, list) and res:
            return res[0]
        return res if res else None

    @staticmethod
    def get_plano_by_id(id_plano: str) -> Optional[Dict[str, Any]]:
        """Find plano by primary key id_plano."""
        query = "SELECT * FROM plano WHERE id_plano = %s;"
        return fetch_one(query, (id_plano,))

    @staticmethod
    def get_modelo2d_by_plano_id(id_plano: str) -> Optional[Dict[str, Any]]:
        """Find associated modelo2d record by id_plano."""
        query = "SELECT * FROM modelo2d WHERE id_plano = %s ORDER BY id_modelo2d DESC LIMIT 1;"
        return fetch_one(query, (id_plano,))

    @staticmethod
    def get_modelo2d_by_id(id_modelo2d: str) -> Optional[Dict[str, Any]]:
        """Find modelo2d record by primary key id_modelo2d."""
        query = "SELECT * FROM modelo2d WHERE id_modelo2d = %s;"
        return fetch_one(query, (id_modelo2d,))


