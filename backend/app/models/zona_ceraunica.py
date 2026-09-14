from dataclasses import dataclass
from typing import Optional


@dataclass
class ZonaCeraunica:
    id_zona: Optional[int] = None
    nombre: str = ""
    ng: float = 2.5
    ciudad: Optional[str] = None

