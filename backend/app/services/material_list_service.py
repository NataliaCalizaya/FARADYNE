from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

ARANDELAS_POR_PARARRAYO = 2

Catalogo = Dict[Tuple[str, Optional[float]], Optional[str]]


def _fmt_altura(altura: float) -> str:
    """1.5 -> '1,50' (formato es-AR)."""
    return f"{altura:.2f}".replace(".", ",")


def _codigo(catalogo: Catalogo, clave: str, altura: Optional[float] = None) -> Optional[str]:
    """Código exacto por (clave, altura); si no hay, el genérico (clave, None)."""
    return catalogo.get((clave, altura)) or catalogo.get((clave, None))


def _item(codigo: Optional[str], descripcion: str, cantidad: int) -> Dict[str, Any]:
    return {"codigo": codigo, "descripcion": descripcion, "cantidad": cantidad, "unidad": "un"}


def calcular_listado_materiales(
    mastiles: List[Dict[str, Any]], catalogo: Optional[Catalogo] = None
) -> List[Dict[str, Any]]:
    """Cómputo de materiales a partir de los mástiles guardados (dicts de MastilRepository).

    Por cada pararrayo: 1 pararrayo, 1 caño galvanizado (de la altura del mástil),
    1 soporte de techo, 1 terminal de aluminio y 2 arandelas bimetálicas.
    Los códigos salen de la tabla material_catalogo.
    """
    if not mastiles:
        return []

    catalogo = catalogo or {}
    total = len(mastiles)
    items: List[Dict[str, Any]] = []

    por_tipo = Counter(m["tipo"] for m in mastiles)
    for tipo, cant in sorted(por_tipo.items()):
        if tipo.lower() == "franklin":
            desc = 'Pararrayo tipo Franklin 5 puntas encastre Ø 3/4"'
        else:
            desc = f'Pararrayo tipo {tipo} encastre Ø 3/4"'
        items.append(_item(_codigo(catalogo, f"pararrayo_{tipo.lower()}"), desc, cant))

    por_altura = Counter(round(m["altura"], 2) for m in mastiles)
    for altura, cant in sorted(por_altura.items()):
        items.append(
            _item(
                _codigo(catalogo, "mastil_galvanizado", altura),
                f"Mástil {_fmt_altura(altura)} m caño galvanizado para pararrayos",
                cant,
            )
        )

    items.append(
        _item(
            _codigo(catalogo, "soporte_mastil_techo"),
            "Soporte para mástil de pararrayos para techo",
            total,
        )
    )
    items.append(
        _item(_codigo(catalogo, "terminal_aluminio_50"), 'Terminal de aluminio 50 mm² Ø 1/2"', total)
    )
    items.append(
        _item(
            _codigo(catalogo, "arandela_bimetalica"),
            'Arandela bimetálica Ø 1/2"',
            total * ARANDELAS_POR_PARARRAYO,
        )
    )
    return items