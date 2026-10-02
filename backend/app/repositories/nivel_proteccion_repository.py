from typing import Any, Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.nivel_de_proteccion import NivelDeProteccion
from app.models.proyecto import Proyecto
from app.models.zona_ceraunica import ZonaCeraunica
from app.repositories.utils import execute_returning_one, to_dict


class NivelProteccionRepository:

    @staticmethod
    def get_proyecto_by_id(db: Session, id_proyecto: int) -> Optional[Dict[str, Any]]:
        """Fila completa de 'proyecto' por id_proyecto."""
        return to_dict(db.get(Proyecto, id_proyecto))

    @staticmethod
    def get_ubicacion_by_proyecto_id(db: Session, id_proyecto: int) -> Optional[Dict[str, Any]]:
        """Trae solo id/nombre/ubicacion del proyecto.

        Se usa para mostrar la ubicación junto al Ng adoptado en el Paso 1
        del cálculo de Nivel de Protección (HU04), sin traer la fila entera.
        """
        stmt = select(Proyecto.id_proyecto, Proyecto.nombre, Proyecto.ubicacion).where(
            Proyecto.id_proyecto == id_proyecto
        )
        row = db.execute(stmt).mappings().first()
        return dict(row) if row else None

    @staticmethod
    def get_zona_ceraunica_by_id(db: Session, id_zona: int) -> Optional[Dict[str, Any]]:
        """Zona ceráunica por PK (columnas: id_zona, nombre, ng, ciudad)."""
        return to_dict(db.get(ZonaCeraunica, id_zona))

    @staticmethod
    def get_zona_ceraunica_by_departamento(db: Session, id_proyecto: int) -> Optional[Dict[str, Any]]:
        """Busca la zona ceráunica (y su Ng) a partir de la localidad real
        cargada en el proyecto (proyecto.localidad), matcheando contra
        zona_ceraunica.ciudad.

        (El nombre del método es histórico: zona_ceraunica no tiene columna
        'departamento', el match se hace por localidad/ciudad.)

        Si la localidad del proyecto no matchea ninguna zona real, devuelve
        None y el llamador debe informar el error en vez de inventar un Ng.
        """
        stmt = (
            select(ZonaCeraunica)
            .select_from(Proyecto)
            .join(
                ZonaCeraunica,
                func.lower(ZonaCeraunica.ciudad) == func.lower(Proyecto.localidad),
            )
            .where(Proyecto.id_proyecto == id_proyecto)
            .limit(1)
        )
        return to_dict(db.scalars(stmt).first())

    @staticmethod
    def get_dimensiones_by_proyecto_id(db: Session, id_proyecto: int) -> Optional[Dict[str, Any]]:
        """L/W/H ya calculadas y persistidas para el proyecto, si existen.

        Se usa para no tener que volver a leer/parsear el Modelo3D en cada
        cálculo de HU04: si el proyecto ya tiene un registro guardado, se
        reusan esas dimensiones."""
        stmt = select(
            NivelDeProteccion.longitud_edificacion,
            NivelDeProteccion.anchura_edificacion,
            NivelDeProteccion.altura_edificacion,
        ).where(NivelDeProteccion.id_proyecto == id_proyecto)
        row = db.execute(stmt).mappings().first()
        return dict(row) if row else None

    @staticmethod
    def save_nivel_proteccion(
        db: Session,
        id_proyecto: int,
        id_zona: Optional[int],
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
        """Inserta o actualiza el nivel de protección calculado del proyecto.

        nivel_de_proteccion.id_proyecto es UNIQUE (un cálculo por proyecto),
        por eso es un único upsert atómico.

        `nivel_proteccion` = nivel finalmente elegido (recomendado o el que
        el usuario haya seleccionado en la grilla). La BD solo acepta
        'I', 'II', 'III' o 'IV' (CHECK).
        `nivel_proteccion_recomendado` = lo que dio el procedimiento F.1, se
        guarda aparte para no perder esa info si el usuario elige otro nivel.
        `factor_a_e` es JSONB: {"a":.., "b":.., "c":.., "d":.., "e":..}.
        `longitud/anchura/altura_edificacion` quedan persistidas para no
        tener que volver a pedirle las dimensiones al Modelo3D en cada
        cálculo o GET posterior.
        """
        stmt = pg_insert(NivelDeProteccion).values(
            id_proyecto=id_proyecto,
            id_zona=id_zona,
            nivel_proteccion=nivel_proteccion,
            nivel_proteccion_recomendado=nivel_proteccion_recomendado,
            nd=nd,
            nc=nc,
            ae=ae,
            eficiencia_minima=eficiencia_minima,
            radio_esfera=radio_esfera,
            factor_a_e=factor_a_e,
            margen_lateral=margen_lateral,
            longitud_edificacion=longitud_edificacion,
            anchura_edificacion=anchura_edificacion,
            altura_edificacion=altura_edificacion,
        )
        columnas_a_actualizar = (
            "id_zona", "nivel_proteccion", "nivel_proteccion_recomendado",
            "nd", "nc", "ae", "eficiencia_minima", "radio_esfera", "factor_a_e",
            "margen_lateral", "longitud_edificacion", "anchura_edificacion",
            "altura_edificacion",
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["id_proyecto"],
            set_={col: getattr(stmt.excluded, col) for col in columnas_a_actualizar},
        ).returning(NivelDeProteccion.__table__)
        return execute_returning_one(db, stmt)

    @staticmethod
    def get_nivel_proteccion_by_proyecto_id(db: Session, id_proyecto: int) -> Optional[Dict[str, Any]]:
        """Cálculo guardado del proyecto (id_proyecto es UNIQUE: a lo sumo una fila)."""
        stmt = select(NivelDeProteccion).where(NivelDeProteccion.id_proyecto == id_proyecto)
        return to_dict(db.scalars(stmt).first())
