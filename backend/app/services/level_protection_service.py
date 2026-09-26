"""
Servicio de cálculo de Nivel de Protección contra Descargas Atmosféricas (SPDA).

Implementa el procedimiento del Anexo A (Tabla A.1), Anexo B (áreas colectoras
equivalentes Ae, incisos B.1.1 / B.1.2) y Anexo E/F (factores A-B-C-D-E y
procedimiento F.1), según IEC 62305-1 a 4:2010 / IRAM 2184-1 a 4 / AEA 92305-1 a 4.

IMPORTANTE - nombres de factores:
Los factores A, B, C, D, E de las Tablas E.1 a E.5 del Anexo (ocupación,
construcción, contenido, localización, topografía) NO son los mismos que los
antiguos Cb/Cc/Cd/Ce de la versión previa de este archivo. Este módulo usa
exclusivamente los 5 factores del Anexo, que el usuario selecciona en el
formulario (HU04).
"""

import math
from typing import Any, Dict, Optional, Tuple


# ---------------------------------------------------------------------------
# Tabla A.1 — Niveles de protección, radios de esfera rodante y corrientes
# ---------------------------------------------------------------------------
NIVELES_TABLA_A1: Dict[str, Dict[str, Any]] = {
    "I+": {
        "radio_esfera_r": 20.0,
        "corriente_minima_ka": 3.0,
        "probabilidad_pct": 99,
        "rango_eficiencia": "0.98 < E ≤ 1.00",
        "descripcion": "Nivel I + medidas complementarias",
    },
    "I": {
        "radio_esfera_r": 20.0,
        "corriente_minima_ka": 3.0,
        "probabilidad_pct": 99,
        "rango_eficiencia": "0.95 < E ≤ 0.98",
        "descripcion": "Nivel I",
    },
    "II": {
        "radio_esfera_r": 30.0,
        "corriente_minima_ka": 5.0,
        "probabilidad_pct": 97,
        "rango_eficiencia": "0.90 < E ≤ 0.95",
        "descripcion": "Nivel II",
    },
    "III": {
        "radio_esfera_r": 45.0,
        "corriente_minima_ka": 10.0,
        "probabilidad_pct": 91,
        "rango_eficiencia": "0.80 < E ≤ 0.90",
        "descripcion": "Nivel III",
    },
    "IV": {
        "radio_esfera_r": 60.0,
        "corriente_minima_ka": 15.0,
        "probabilidad_pct": 84,
        "rango_eficiencia": "0.00 < E ≤ 0.80",
        "descripcion": "Nivel IV",
    },
}


def determine_margin_lateral(height: float) -> int:
    """Determina el margen lateral (3H o 1H) según Anexo G AEA 92305-11:
    - 2 m ≤ H ≤ 10 m  -> margen lateral 3 (Ae más amplia, Fig. B.1)
    - 11 m ≤ H ≤ 60 m -> margen lateral 1 (Ae más ajustada, Fig. B.4)
    Fuera de ese rango se adopta 3 por defecto (criterio habitual del proyecto).
    """
    if height is None or height <= 0:
        return 3
    if 2 <= height <= 10:
        return 3
    if 11 <= height <= 60:
        return 1
    return 3


def formula_ae_por_margen(margin_lateral: int) -> str:
    """Texto de la fórmula de Ae aplicada según el margen lateral. Separada
    de calculate_equivalent_collection_area_ae para poder reconstruir el
    texto solo a partir de `margen_lateral` (p. ej. al releer un registro ya
    guardado, donde no se persisten L/W/H)."""
    if margin_lateral == 1:
        return "Ae = L·W + 2H·(L+W) + π·H²  [margen lateral H=1, 11m ≤ H ≤ 60m]"
    return "Ae = L·W + 6H·(L+W) + 9·π·H²  [margen lateral H=3, 2m ≤ H ≤ 10m]"


def calculate_equivalent_collection_area_ae(
    length: float, width: float, height: float, margin_lateral: int = 3
) -> Tuple[float, str]:
    """Calcula el área colectora equivalente Ae (m²) y devuelve también el
    texto de la fórmula aplicada, para trazabilidad frente al usuario.

    margin_lateral = 3 -> Ae = L·W + 6H(L+W) + 9·π·H²   (Fig. B.1, alturas 2-10 m)
    margin_lateral = 1 -> Ae = L·W + 2H(L+W) + π·H²      (Fig. B.4, alturas 11-60 m)
    """
    if length <= 0 or width <= 0 or height <= 0:
        return 0.0, ""

    area_base = length * width
    if margin_lateral == 1:
        ae = area_base + 2.0 * height * (length + width) + math.pi * (height ** 2)
    else:
        ae = area_base + 6.0 * height * (length + width) + 9.0 * math.pi * (height ** 2)

    return round(ae, 2), formula_ae_por_margen(margin_lateral)


def calculate_direct_strikes_nd(density_ng: float, area_ae: float) -> float:
    """Nd = Ng * Ae * 10^-6  (descargas directas/año) — Anexo D."""
    return round(density_ng * area_ae * 1e-6, 8)


def calculate_tolerable_frequency_nc(
    nd: float,
    factor_a: float,
    factor_b: float,
    factor_c: float,
    factor_d: float,
    factor_e: float,
) -> float:
    """Nc = (A · B · C · D · E) · Nd — Anexo E."""
    return round(factor_a * factor_b * factor_c * factor_d * factor_e * nd, 8)


def determine_nivel_recomendado(nd: float, nc: float) -> Dict[str, Any]:
    """Procedimiento F.1: compara Nd contra Nc.
    - Si Nd ≤ Nc -> no se exige SPCR (se informa Nivel IV como referencia).
    - Si Nd > Nc -> se calcula E = 1 - (Nc/Nd) y se ubica en la Tabla F.1.

    Es la única fuente de verdad para `requiere_spcr` / nivel recomendado:
    tanto el cálculo inicial (calculate_risk) como una relectura posterior
    (a partir de nd/nc ya guardados) deben pasar por acá en vez de
    reimplementar la comparación.
    """
    if nd <= 0 or nd <= nc:
        return {
            "requiere_spcr": False,
            "nivel_recomendado": "IV",
            "eficiencia_e": None,
            "justificacion": (
                f"Nd ({nd}) ≤ Nc ({nc}): según el inciso F.1 la estructura no "
                "requiere SPCR obligatorio. Cualquier nivel de protección es "
                "suficiente; se informa Nivel IV como referencia mínima."
            ),
        }

    eficiencia = 1.0 - (nc / nd)

    if eficiencia > 0.98:
        nivel = "I+"
    elif eficiencia > 0.95:
        nivel = "I"
    elif eficiencia > 0.90:
        nivel = "II"
    elif eficiencia > 0.80:
        nivel = "III"
    else:
        nivel = "IV"

    return {
        "requiere_spcr": True,
        "nivel_recomendado": nivel,
        "eficiencia_e": round(eficiencia, 4),
        "justificacion": (
            f"Nd ({nd}) > Nc ({nc}): se requiere SPCR. "
            f"E = 1 - (Nc/Nd) = {eficiencia:.4f} → Nivel {nivel} según Tabla F.1."
        ),
    }


class level_protection_service:
    """Servicio de cálculo de riesgo y Nivel de Protección SPDA (HU04)."""

    @staticmethod
    def obtener_tabla_niveles() -> Dict[str, Dict[str, Any]]:
        """Expone la Tabla A.1 para que el frontend arme la grilla de
        selección libre de Nivel de Protección (radio, corriente, probabilidad)."""
        return NIVELES_TABLA_A1

    @staticmethod
    def datos_nivel(nivel: str) -> Dict[str, Any]:
        """Devuelve radio/corriente/probabilidad para un nivel elegido
        libremente por el usuario (puede diferir del recomendado)."""
        return NIVELES_TABLA_A1.get(nivel, NIVELES_TABLA_A1["IV"])

    @staticmethod
    def calculate_risk(
        length: float,
        width: float,
        height: float,
        density_ng: float,
        factor_a: float = 1.0,
        factor_b: float = 1.0,
        factor_c: float = 1.0,
        factor_d: float = 1.0,
        factor_e: float = 1.0,
        margin_lateral: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Ejecuta el cálculo completo Ae -> Nd -> Nc -> Nivel recomendado."""

        if margin_lateral is None:
            margin_lateral = determine_margin_lateral(height)

        ae, formula_ae = calculate_equivalent_collection_area_ae(
            length, width, height, margin_lateral
        )
        nd = calculate_direct_strikes_nd(density_ng, ae)
        nc = calculate_tolerable_frequency_nc(
            nd, factor_a, factor_b, factor_c, factor_d, factor_e
        )
        recomendacion = determine_nivel_recomendado(nd, nc)

        nivel_recomendado = recomendacion["nivel_recomendado"]
        datos_nivel = NIVELES_TABLA_A1.get(nivel_recomendado, NIVELES_TABLA_A1["IV"])

        return {
            "longitud": length,
            "anchura": width,
            "altura": height,
            "margen_lateral": margin_lateral,
            "formula_area_utilizada": formula_ae,
            "area_equivalente_ae": ae,
            "densidad_ng": density_ng,
            "frecuencia_impactos_nd": nd,
            "frecuencia_tolerable_nc": nc,
            "requiere_spcr": recomendacion["requiere_spcr"],
            "eficiencia_proteccion": recomendacion["eficiencia_e"],
            "nivel_proteccion_recomendado": nivel_recomendado,
            "justificacion_nivel": recomendacion["justificacion"],
            "radio_esfera_rodante_r": datos_nivel["radio_esfera_r"],
            "factores_riesgo": {
                "a": factor_a,
                "b": factor_b,
                "c": factor_c,
                "d": factor_d,
                "e": factor_e,
            },
            "tabla_niveles": NIVELES_TABLA_A1,
        }