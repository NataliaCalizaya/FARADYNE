from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class NivelDeProteccion:
    id_nivel_proteccion: Optional[int] = None
    # Nivel finalmente elegido (recomendado o el que haya seleccionado el
    # usuario libremente en la grilla). Antes se llamaba `nivel`.
    nivel_proteccion: Optional[str] = None
    # Nivel que dio el cálculo F.1, se guarda aparte para no perder esa
    # información una vez que el usuario elige un nivel distinto.
    nivel_proteccion_recomendado: Optional[str] = None
    nd: float = 0.0
    nc: float = 0.0
    ae: float = 0.0
    eficiencia_minima: float = 0.0
    radio_esfera: float = 0.0
    # JSONB con los 5 factores del Anexo E: {"a": .., "b": .., "c": .., "d": .., "e": ..}
    factor_a_e: Dict[str, float] = field(default_factory=dict)
    margen_lateral: float = 0.0
    # L/W/H persistidas para no tener que volver a leer/parsear el Modelo3D
    # en cada cálculo (ver NivelProteccionRepository.get_dimensiones_by_proyecto_id).
    longitud_edificacion: float = 0.0
    anchura_edificacion: float = 0.0
    altura_edificacion: float = 0.0
    id_proyecto: Optional[int] = None
    id_zona: Optional[int] = None