"""app.repositories.resultado_simulacion_repository

Persistencia del resultado de la cobertura SPDA en `resultado_simulacion`
(una fila por proyecto; se sobrescribe al volver a confirmar).

Columnas: id_resultado (PK integer), id_proyecto, zonas_protegidas,
zonas_vulnerables, mallas_cobertura (JSONB), fecha_simulacion (timestamp).

Nota: la BD NO tiene UNIQUE sobre id_proyecto (solo un índice), así que
"una fila por proyecto" lo garantiza este upsert manual, no la base.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.resultado_simulacion import ResultadoSimulacion
from app.repositories.utils import commit_or_rollback, to_dict


class ResultadoSimulacionRepository:

    @staticmethod
    def upsert_por_proyecto(
        db: Session,
        id_proyecto: int,
        zonas_protegidas: List[Dict[str, Any]],
        zonas_vulnerables: List[Dict[str, Any]],
        mallas_cobertura: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Actualiza el resultado del proyecto o lo crea si todavía no existe."""
        stmt = (
            select(ResultadoSimulacion)
            .where(ResultadoSimulacion.id_proyecto == id_proyecto)
            .order_by(ResultadoSimulacion.id_resultado.desc())
        )
        existentes = db.scalars(stmt).all()

        if existentes:
            for resultado in existentes:
                resultado.zonas_protegidas = zonas_protegidas
                resultado.zonas_vulnerables = zonas_vulnerables
                resultado.mallas_cobertura = mallas_cobertura
                resultado.fecha_simulacion = func.now()
            principal = existentes[0]
        else:
            principal = ResultadoSimulacion(
                id_proyecto=id_proyecto,
                zonas_protegidas=zonas_protegidas,
                zonas_vulnerables=zonas_vulnerables,
                mallas_cobertura=mallas_cobertura,
            )
            db.add(principal)

        commit_or_rollback(db)
        db.refresh(principal)
        return to_dict(principal)

    @staticmethod
    def get_por_proyecto(db: Session, id_proyecto: int) -> Optional[Dict[str, Any]]:
        stmt = (
            select(ResultadoSimulacion)
            .where(ResultadoSimulacion.id_proyecto == id_proyecto)
            .order_by(ResultadoSimulacion.fecha_simulacion.desc())
            .limit(1)
        )
        return to_dict(db.scalars(stmt).first())
