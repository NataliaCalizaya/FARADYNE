from typing import Any, Dict, Optional
from app.core.database import execute_query, fetch_one, serialize_json


class NivelProteccionRepository:
 
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
    def get_dimensiones_by_proyecto_id(id_proyecto: str) -> Optional[Dict[str, Any]]:
        """L/W/H ya calculadas y persistidas para el proyecto, si existen.

        Se usa para no tener que volver a leer/parsear el Modelo3D en cada
        cálculo de HU04: si el proyecto ya tiene un registro guardado, se
        reusan esas dimensiones."""
        query = """
            SELECT longitud_edificacion, anchura_edificacion, altura_edificacion
            FROM nivel_de_proteccion
            WHERE id_proyecto = %s
            ORDER BY id_nivel_proteccion DESC
            LIMIT 1;
        """
        return fetch_one(query, (id_proyecto,))

    @staticmethod
    def save_nivel_proteccion(
        id_proyecto: str,
        id_zona: Optional[str],
        nivel_proteccion: str,
        nivel_proteccion_recomendado: str,
        nd: float,
        nc: float,
        ae: float,
        eficiencia_minima: Optional[float],
        radio_esfera: float,
        factor_a_e: Dict[str, float],
        margen_lateral: float,
        longitud_edificacion: float,
        anchura_edificacion: float,
        altura_edificacion: float,
    ) -> Dict[str, Any]:
        """Insert or update calculated protection level entry for project in
        table 'nivel_de_proteccion'.

        `nivel_proteccion` = nivel finalmente elegido (recomendado o el que
        el usuario haya seleccionado libremente en la grilla).
        `nivel_proteccion_recomendado` = lo que dio el procedimiento F.1, se
        guarda aparte para no perder esa info si el usuario elige otro nivel.
        `factor_a_e` es JSONB: {"a":.., "b":.., "c":.., "d":.., "e":..}.
        `longitud/anchura/altura_edificacion` quedan persistidas para no
        tener que volver a pedirle las dimensiones al Modelo3D en cada
        cálculo o GET posterior.
        """
        factor_a_e_json = serialize_json(factor_a_e)

        check_query = "SELECT id_nivel_proteccion FROM nivel_de_proteccion WHERE id_proyecto = %s LIMIT 1;"
        existing = fetch_one(check_query, (id_proyecto,))

        if existing:
            update_query = """
                UPDATE nivel_de_proteccion
                SET id_zona = %s,
                    nivel_proteccion = %s,
                    nivel_proteccion_recomendado = %s,
                    nd = %s,
                    nc = %s,
                    ae = %s,
                    eficiencia_minima = %s,
                    radio_esfera = %s,
                    factor_a_e = %s,
                    margen_lateral = %s,
                    longitud_edificacion = %s,
                    anchura_edificacion = %s,
                    altura_edificacion = %s
                WHERE id_nivel_proteccion = %s
                RETURNING *;
            """
            params = (
                id_zona,
                nivel_proteccion,
                nivel_proteccion_recomendado,
                nd,
                nc,
                ae,
                eficiencia_minima,
                radio_esfera,
                factor_a_e_json,
                margen_lateral,
                longitud_edificacion,
                anchura_edificacion,
                altura_edificacion,
                existing["id_nivel_proteccion"],
            )
            res = execute_query(update_query, params, fetch=True)
            return res[0] if isinstance(res, list) and res else (res if res else {})
        else:
            insert_query = """
                INSERT INTO nivel_de_proteccion (
                    id_proyecto, id_zona, nivel_proteccion, nivel_proteccion_recomendado,
                    nd, nc, ae, eficiencia_minima, radio_esfera, factor_a_e, margen_lateral,
                    longitud_edificacion, anchura_edificacion, altura_edificacion
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *;
            """
            params = (
                id_proyecto,
                id_zona,
                nivel_proteccion,
                nivel_proteccion_recomendado,
                nd,
                nc,
                ae,
                eficiencia_minima,
                radio_esfera,
                factor_a_e_json,
                margen_lateral,
                longitud_edificacion,
                anchura_edificacion,
                altura_edificacion,
            )
            res = execute_query(insert_query, params, fetch=True)
            return res[0] if isinstance(res, list) and res else (res if res else {})

    @staticmethod
    def get_nivel_proteccion_by_proyecto_id(id_proyecto: str) -> Optional[Dict[str, Any]]:
        """Fetch saved calculation by project ID (el más reciente)."""
        query = "SELECT * FROM nivel_de_proteccion WHERE id_proyecto = %s ORDER BY id_nivel_proteccion DESC LIMIT 1;"
        return fetch_one(query, (id_proyecto,))