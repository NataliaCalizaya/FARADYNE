from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional


@dataclass
class ResultadoSimulacion:
    id_resultado: Optional[int] = None
    zonas_protegidas: List[Dict[str, Any]] = field(default_factory=list)
    zonas_vulnerables: List[Dict[str, Any]] = field(default_factory=list)
    mallas_cobertura: List[Dict[str, Any]] = field(default_factory=list)
    fecha_simulacion: Optional[datetime] = None
    id_proyecto: Optional[int] = None

