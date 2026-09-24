from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


# @dataclass
# class Modelo2D:
#     id_modelo2d: Optional[int] = None
#     poligonos: List[Dict[str, Any]] = field(default_factory=list)
#     lineas: List[Dict[str, Any]] = field(default_factory=list)
#     capas: List[str] = field(default_factory=list)
#     colores: List[Dict[str, Any]] = field(default_factory=list)
#     cotas_altura: List[Dict[str, Any]] = field(default_factory=list)
#     validado: bool = False
#     id_plano: Optional[int] = None
@dataclass
class Modelo2D:

    id_modelo2d: Optional[int] = None
    poligonos: List[Dict[str, Any]] = field(default_factory=list)
    lineas: List[Dict[str, Any]] = field(default_factory=list)
    capas: List[Dict[str, Any]] = field(default_factory=list)
    colores: List[Dict[str, Any]] = field(default_factory=list)
    cotas_altura: List[Dict[str, Any]] = field(default_factory=list)
    validado: bool = False
    id_plano: Optional[int] = None

