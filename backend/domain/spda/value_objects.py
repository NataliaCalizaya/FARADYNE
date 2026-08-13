from pydantic import BaseModel
from .entities import SPDALevel

class NivelProteccion(BaseModel):
    level: SPDALevel
    rolling_sphere_radius: float

def get_radio_esfera(level: SPDALevel) -> float:
    if level == SPDALevel.I:
        return 20.0
    elif level == SPDALevel.II:
        return 30.0
    elif level == SPDALevel.III:
        return 45.0
    elif level == SPDALevel.IV:
        return 60.0
    return 60.0
