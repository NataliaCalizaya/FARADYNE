"""app.repositories.resultado_simulacion_repository

Persistencia del resultado de la cobertura SPDA en `resultado_simulacion`
(una fila por proyecto; se sobrescribe al volver a confirmar).

Columnas esperadas: id_resultado, id_proyecto, zonas_protegidas,
zonas_vulnerables, mallas_cobertura (JSONB), fecha_simulacion.
"""

import json
from typing import Any, Dict, List, Optional

from app.core.database import execute_query, fetch_one


def _json(valor: Any) -> str:
    return json.dumps(valor, default=str, ensure_ascii=False)


def _primera_fila(res: Any) -> Optional[Dict[str, Any]]:
    if isinstance(res, list):
        return res[0] if res else None
    return res or None


class ResultadoSimulacionRepository:

    @staticmethod
    def upsert_por_proyecto(
        id_proyecto: str,
        zonas_protegidas: List[Dict[str, Any]],
        zonas_vulnerables: List[Dict[str, Any]],
        mallas_cobertura: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Actualiza el resultado del proyecto o lo crea si todavía no existe."""
        params = (_json(zonas_protegidas), _json(zonas_vulnerables), _json(mallas_cobertura))

        actualizado = _primera_fila(execute_query(
            """
            UPDATE resultado_simulacion
               SET zonas_protegidas = %s::jsonb,
                   zonas_vulnerables = %s::jsonb,
                   mallas_cobertura = %s::jsonb,
                   fecha_simulacion = NOW()
             WHERE id_proyecto = %s
            RETURNING *;
            """,
            (*params, id_proyecto),
            fetch=True,
        ))
        if actualizado:
            return actualizado

        return _primera_fila(execute_query(
            """
            INSERT INTO resultado_simulacion
                (zonas_protegidas, zonas_vulnerables, mallas_cobertura, fecha_simulacion, id_proyecto)
            VALUES (%s::jsonb, %s::jsonb, %s::jsonb, NOW(), %s)
            RETURNING *;
            """,
            (*params, id_proyecto),
            fetch=True,
        )) or {}

    @staticmethod
    def get_por_proyecto(id_proyecto: str) -> Optional[Dict[str, Any]]:
        return fetch_one(
            "SELECT * FROM resultado_simulacion WHERE id_proyecto = %s "
            "ORDER BY fecha_simulacion DESC LIMIT 1;",
            (id_proyecto,),
        )
