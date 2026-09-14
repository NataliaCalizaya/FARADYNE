from typing import Any, Dict, Optional
from app.core.database import execute_query, fetch_one, serialize_json


class NivelProteccionRepository:

    @staticmethod
    def get_zona_ceraunica_by_id(id_zona: str) -> Optional[Dict[str, Any]]:
        """Fetch zona_ceraunica entry by primary key ID id_zona."""
        query = "SELECT * FROM zona_ceraunica WHERE id_zona = %s;"
        return fetch_one(query, (id_zona,))

    @staticmethod
    def get_zona_ceraunica_by_departamento(departamento: str) -> Optional[Dict[str, Any]]:
        """Fetch or create default zona_ceraunica by department/city name."""
        query = "SELECT * FROM zona_ceraunica WHERE LOWER(nombre) = LOWER(%s) OR LOWER(ciudad) = LOWER(%s) LIMIT 1;"
        zona = fetch_one(query, (departamento, departamento))
        if not zona:
            insert_query = """
                INSERT INTO zona_ceraunica (nombre, ng, ciudad)
                VALUES (%s, 2.5, %s)
                RETURNING *;
            """
            res = execute_query(insert_query, (departamento, departamento), fetch=True)
            zona = res[0] if isinstance(res, list) and res else (res if res else None)
        return zona

    @staticmethod
    def save_nivel_proteccion(
        id_proyecto: str,
        id_zona: Optional[str],
        longitud: float = 0.0,
        anchura: float = 0.0,
        altura: float = 0.0,
        area_ae: float = 0.0,
        nd: float = 0.0,
        nc: float = 0.0,
        requiere_spcr: bool = False,
        nivel_calculado: Optional[str] = "Nivel II",
        eficiencia: Optional[float] = 0.95,
        factores_riesgo: Optional[Dict[str, Any]] = None,
        radio_esfera: float = 30.0,
        factor_a_e: float = 1.0,
        margen_lateral: float = 0.0,
    ) -> Dict[str, Any]:
        """Insert or update calculated protection level entry for project in table 'nivel_de_proteccion'."""
        check_query = "SELECT id_nivel_proteccion FROM nivel_de_proteccion WHERE id_proyecto = %s LIMIT 1;"
        existing = fetch_one(check_query, (id_proyecto,))

        if existing:
            update_query = """
                UPDATE nivel_de_proteccion
                SET id_zona = %s,
                    nivel = %s,
                    nd = %s,
                    nc = %s,
                    ae = %s,
                    eficiencia_minima = %s,
                    radio_esfera = %s,
                    factor_a_e = %s,
                    margen_lateral = %s
                WHERE id_nivel_proteccion = %s
                RETURNING *;
            """
            params = (
                id_zona,
                nivel_calculado,
                nd,
                nc,
                area_ae,
                eficiencia,
                radio_esfera,
                factor_a_e,
                margen_lateral,
                existing["id_nivel_proteccion"],
            )
            res = execute_query(update_query, params, fetch=True)
            return res[0] if isinstance(res, list) and res else (res if res else {})
        else:
            insert_query = """
                INSERT INTO nivel_de_proteccion (
                    id_proyecto, id_zona, nivel, nd, nc, ae,
                    eficiencia_minima, radio_esfera, factor_a_e, margen_lateral
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *;
            """
            params = (
                id_proyecto,
                id_zona,
                nivel_calculado,
                nd,
                nc,
                area_ae,
                eficiencia,
                radio_esfera,
                factor_a_e,
                margen_lateral,
            )
            res = execute_query(insert_query, params, fetch=True)
            return res[0] if isinstance(res, list) and res else (res if res else {})

    @staticmethod
    def get_nivel_proteccion_by_proyecto_id(id_proyecto: str) -> Optional[Dict[str, Any]]:
        """Fetch saved calculation by project ID."""
        query = "SELECT * FROM nivel_de_proteccion WHERE id_proyecto = %s ORDER BY id_nivel_proteccion DESC LIMIT 1;"
        return fetch_one(query, (id_proyecto,))

