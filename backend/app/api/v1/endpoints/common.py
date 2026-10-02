from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException, status


def to_int(valor: Any, campo: str = "id") -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"'{campo}' debe ser un entero válido (recibido: {valor!r}).",
        )


def extraer_dimensiones_modelo3d(
    modelo3d: Dict[str, Any],
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Longitud, anchura y altura desde `geometria_volumetrica` (bbox / levels).

    La altura sale de `altura_h` si es > 0; si no, de la mayor cota en `levels`.
    """
    geometria = modelo3d.get("geometria_volumetrica") or {}

    length = width = None
    bbox = geometria.get("bbox")
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        bx0, by0, bx1, by1 = bbox
        length = round(float(bx1) - float(bx0), 2)
        width = round(float(by1) - float(by0), 2)

    height = modelo3d.get("altura_h")
    if not height or float(height) <= 0:
        alturas = [float(v) for v in (geometria.get("levels") or []) if v is not None]
        height = max(alturas) if alturas else None

    return length, width, (float(height) if height else None)
