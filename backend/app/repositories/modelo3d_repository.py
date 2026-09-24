from typing import Any, Dict, Optional
from app.core.database import execute_query, fetch_one, serialize_json
import json

class Modelo3DRepository:
    @staticmethod
    def create_modelo3d(
        id_modelo2d: str,
        geometria_volumetrica: Optional[Dict[str, Any]] = None,
        vista_defecto: Optional[Dict[str, Any]] = None,
        escala: float = 1.0,
        altura_h: float = 0.0,
    ) -> Dict[str, Any]:
        """Save generated 3D volumetric mesh in table 'modelo3d' using parameterized SQL."""
        if geometria_volumetrica is None:
            geometria_volumetrica = {}
            
        if vista_defecto is None:
            vista_defecto = {"camera": [50, 50, 50], "target": [0, 0, 0]}

        query = """
        INSERT INTO modelo3d (id_modelo2d, geometria_volumetrica, vista_defecto, creado_en, actualizado_en)
        VALUES (%(id_modelo2d)s, %(geometria_volumetrica)s, %(vista_defecto)s, NOW(), NOW())
        ON CONFLICT (id_modelo2d) 
        DO UPDATE SET 
            geometria_volumetrica = EXCLUDED.geometria_volumetrica,
            vista_defecto = EXCLUDED.vista_defecto,
            actualizado_en = NOW()
        RETURNING *;
        """
        # params = (
        #     id_modelo2d,
        #     serialize_json(geometria_volumetrica),
        #     serialize_json(vista_defecto),
        #     escala,
        #     altura_h,
        # )
        # Usamos un DICCIONARIO. Las llaves deben coincidir exactamente con los %(nombre)s del query.
        # NOTA: Quité 'escala' y 'altura_h' de aquí porque no los estás insertando en el SQL.
        params = {
            "id_modelo2d": id_modelo2d,
            "geometria_volumetrica": serialize_json(geometria_volumetrica),
            "vista_defecto": serialize_json(vista_defecto)
        }
        
        res = execute_query(query, params, fetch=True)
        return res[0] if isinstance(res, list) and res else (res if res else {})


        
    @staticmethod
    def update_modelo3d(
        id_modelo3d: str,
        geometria_volumetrica: Dict[str, Any],
        vista_defecto: Dict[str, Any]
    ) -> dict:
        """
        Actualiza la geometría y la vista por defecto de un modelo 3D existente.
        """
        query = """
            UPDATE modelo3d 
            SET geometria_volumetrica = %s::jsonb,
                vista_defecto = %s::jsonb,
                creado_en = CURRENT_DATE
            WHERE id_modelo3d = %s
            RETURNING *;
        """
        
        # Serializamos los diccionarios a texto JSON para la base de datos
        params = (
            serialize_json(geometria_volumetrica),
            serialize_json(vista_defecto),
            id_modelo3d
        )
        
        # Ejecutamos el update y pedimos que nos devuelva la fila actualizada
        resultado = execute_query(query, params, fetch=True)
        
        return resultado if resultado else {}

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
# Asegúrate de tener importado fetch_one arriba en tu archivo
# from app.core.database import fetch_one

    @staticmethod
    def get_modelo3d_by_modelo2d_id(id_modelo2d: str) -> dict:
        """
        Busca si ya existe un modelo 3D asociado a un plano 2D específico.
        """
        query = """
            SELECT * FROM modelo3d 
            WHERE id_modelo2d = %s;
        """
        
        # Usamos tu función fetch_one que ya maneja la conexión y el retorno del diccionario
        resultado = fetch_one(query, (id_modelo2d,))
        
        return resultado if resultado else {}

    # def update_vista_defecto(id_modelo3d: str, vista_defecto: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    #     """Fetch model by primary key id_modelo3d for camera reset view."""
    #     return Modelo3DRepository.get_modelo3d_by_id(id_modelo3d)
    @staticmethod
    def update_vista_defecto(id_modelo3d: str, vista_defecto: dict) -> dict:
        """
        Actualiza la columna jsonb 'vista_defecto' en la tabla modelo3d.
        """
        vista_json = json.dumps(vista_defecto)
        # La consulta SQL usa RETURNING * para devolvernos la fila recién actualizada
        query = """
            UPDATE modelo3d 
            SET vista_defecto = %s 
            WHERE id_modelo3d = %s
            RETURNING *;
        """
        resultado = execute_query(query, (vista_json, id_modelo3d), fetch=True)
        return resultado if resultado else {}

