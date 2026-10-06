"""
app.services.spda_service

Servicio de evaluación de cobertura SPDA (HU05) por el Método de la Esfera
Rodante, "por ternas de mástiles".

Geometría (independiente por pieza, sin envolvente global):

  * PARCHE: cada terna de mástiles cuya esfera de radio R, apoyada en sus 3
    puntas, no contiene ninguna otra punta (criterio de esfera vacía, sin
    Delaunay). El parche es el triángulo esférico entre las 3 puntas.

  * UNIÓN: dos ternas que comparten la arista AB se unen con una banda
    toroidal: la esfera pivota sobre AB (tocando siempre A y B) y su centro
    recorre un arco entre los centros de las dos ternas.

  * FALDA: una arista del borde de la malla de ternas que da al exterior del
    edificio (no a un patio) se prolonga hasta el suelo: la esfera pivota sobre
    AB hasta quedar tangente a z = 0. La falda es la banda toroidal más el
    triángulo esférico (A, B, punto de contacto con el suelo).

  * CASQUETE: en un mástil donde terminan dos faldas, la esfera pivota sobre la
    punta apoyada en el suelo (superficie de revolución alrededor de la vertical
    de la punta) y cierra la esquina entre las dos faldas.

Cada pieza se valida por separado y, si falla, no se dibuja ni protege:

    sin_esfera_radio_insuficiente   (diagnóstico) mástiles vecinos muy separados
    sin_esfera_toca_suelo           la superficie llega a z <= 0 (p. ej. en un patio)
    sin_esfera_toca_cubierta        la superficie toca una cubierta
    sin_union_no_apoyable           la esfera no puede pivotar sobre la arista
    sin_falda_*                     la falda / casquete no se puede dibujar

Reglas de la falda:
    * Solo en aristas exteriores; los patios interiores no llevan falda.
    * No se dibuja si la punta supera 2R (la esfera no puede tocar punta y suelo).
    * No se dibuja ninguna si la cota máxima de cubierta supera 60 m (se agrega
      una advertencia: se requiere protección en los laterales).

Evaluación: se muestrea la cubierta (polígonos del Modelo2D). Cada celda queda:

    protegida               por debajo de alguna superficie (terna o falda)
    sobre_la_esfera         la cubierta queda por encima de la superficie
    fuera_de_triangulacion  fuera de cualquier terna o falda
    (o el motivo de la terna descartada que la contiene)

Convención de coordenadas: sistema del Modelo2D/3D (x, y = planta en metros;
z = altura). En el visor (three.js, Y hacia arriba) el punto se dibuja (x, z, -y).
"""

import math
from collections import Counter, defaultdict
from itertools import combinations
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import shapely
from shapely.geometry import MultiPoint, Polygon, box
from shapely.ops import triangulate, unary_union

from app.services.model3d_generator_service import (
    normalize_footprint,
    prepare_region_levels,
    top_plane,
)

Vec3 = Tuple[float, float, float]

EPS_COLINEAL = 1e-6          # |n| mínimo (m²) para considerar 3 puntas no colineales
TOL_Z = 0.05                 # margen de 5 cm
TOL_PUNTA_EN_ESFERA = 1e-3   # m: una punta a menos de R - tol del centro está "dentro"
MAX_MUESTRAS = 6000          # tope de celdas de cubierta a evaluar
Z_SUELO = 0.0                # cota del suelo del modelo

# Falda exterior
ALTURA_MAX_FALDA = 60.0      # m: sobre esta cota máxima de cubierta no hay falda
CIERRE_RENDIJAS = 0.10       # m: cierra rendijas entre polígonos contiguos
ALCANCE_BORDE = 3.0          # m: hasta dónde se busca el borde del techo hacia afuera
PASO_SONDA = 0.05            # m: paso de la sonda que clasifica exterior / patio

# Malla de las superficies para el visor
PASO_TELA = 1.0                  # separación objetivo de la malla (m)
SUBDIV_MIN, SUBDIV_MAX = 6, 32   # lados por arista de un parche
PASO_ANGULAR_RODADO = 2.0        # grados de giro del centro entre filas de una unión
FILAS_MIN, FILAS_MAX = 3, 40
TOL_MISMA_ESFERA = 0.05      # m: centros a menos de esto se consideran la misma esfera

MOTIVO_RADIO = "sin_esfera_radio_insuficiente"
MOTIVO_COLINEAL = "sin_esfera_puntas_colineales"
MOTIVO_NO_APOYABLE = "sin_esfera_no_apoyable"
MOTIVO_TOCA_SUELO = "sin_esfera_toca_suelo"
MOTIVO_TOCA_CUBIERTA = "sin_esfera_toca_cubierta"
MOTIVO_UNION = "sin_union_no_apoyable"
MOTIVO_FALDA_SUELO = "sin_falda_no_alcanza_suelo"
MOTIVO_FALDA_PUNTA = "sin_falda_punta_interior"
MOTIVO_FALDA_CUBIERTA = "sin_falda_toca_cubierta"
MOTIVO_FUERA = "fuera_de_triangulacion"
MOTIVO_SOBRE = "sobre_la_esfera"

MENSAJES_MOTIVO = {
    MOTIVO_RADIO: "que el radio de la esfera no alcanza a tocar las 3 puntas (mástiles muy separados)",
    MOTIVO_COLINEAL: "que las 3 puntas están alineadas",
    MOTIVO_NO_APOYABLE: "que la esfera no puede apoyarse sobre las 3 puntas (diferencia de alturas excesiva)",
    MOTIVO_TOCA_SUELO: "que la esfera llega hasta el suelo entre las puntas (mástiles muy separados)",
    MOTIVO_TOCA_CUBIERTA: "que la esfera toca la cubierta entre las puntas (mástiles muy separados)",
    MOTIVO_UNION: "que la esfera no puede pivotar sobre esta arista sin tocar otra punta",
    MOTIVO_FALDA_SUELO: "que la esfera no puede llegar al suelo pivotando sobre esta arista",
    MOTIVO_FALDA_PUNTA: "otra punta queda dentro de la esfera al bajar la falda",
    MOTIVO_FALDA_CUBIERTA: "la falda toca una cubierta más baja o el borde del techo: falta proteger esa zona",
    MOTIVO_FUERA: "zona fuera de cualquier terna de mástiles",
    MOTIVO_SOBRE: "la cubierta queda por encima de la esfera",
}

# Etiquetas cortas para las advertencias.
ETIQUETAS_MOTIVO = {
    MOTIVO_RADIO: "mástiles muy separados",
    MOTIVO_COLINEAL: "mástiles alineados",
    MOTIVO_NO_APOYABLE: "esfera sin apoyo posible",
    MOTIVO_TOCA_SUELO: "que la esfera llega al suelo",
    MOTIVO_TOCA_CUBIERTA: "que la esfera toca la cubierta",
    MOTIVO_UNION: "que la esfera no puede pivotar sobre la arista",
    MOTIVO_FALDA_SUELO: "que la esfera no llega al suelo",
    MOTIVO_FALDA_PUNTA: "otra punta dentro de la esfera",
    MOTIVO_FALDA_CUBIERTA: "que la falda toca la cubierta",
}

FORMA_PARCHE = "parche_esfera"
FORMA_UNION = "union_esferas"
FORMA_FALDA = "falda_esfera"
FORMA_CASQUETE = "casquete_esfera"

TIPO_FALDA = "falda"
TIPO_CASQUETE = "casquete"
TIPO_FALDA_SIN = "falda_sin_superficie"
TIPO_UNION_SIN = "union_sin_superficie"


# ============================================================
# VECTORES
# ============================================================

def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _mul(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _norm(a: Vec3) -> float:
    return math.sqrt(_dot(a, a))


def _unit(a: Vec3) -> Vec3:
    n = _norm(a)
    return _mul(a, 1.0 / n) if n > 0 else a


def _r3(v) -> List[float]:
    return [round(float(v[0]), 3), round(float(v[1]), 3), round(float(v[2]), 3)]


def _clave_xy(p: Vec3) -> Tuple[float, float]:
    return (round(p[0], 4), round(p[1], 4))


def _punta(m: Dict[str, Any]) -> Vec3:
    return (
        float(m.get("posicion_x", 0.0)),
        float(m.get("posicion_y", 0.0)),
        float(m.get("posicion_z", 0.0)) + float(m.get("altura", 0.0)),
    )


def _limitar(valor: int, minimo: int, maximo: int) -> int:
    return max(minimo, min(maximo, valor))


# ============================================================
# ESFERA POR 3 PUNTOS (port de ESFERA3P.lsp)
# ============================================================

def circuncentro_3d(p1: Vec3, p2: Vec3, p3: Vec3) -> Optional[Vec3]:
    """Centro de la circunferencia que pasa por 3 puntos en el espacio."""
    ab = _sub(p2, p1)
    ac = _sub(p3, p1)
    n = _cross(ab, ac)
    denom = 2.0 * _dot(n, n)
    if abs(denom) < 1e-9:
        return None
    cross_ab = _cross(ab, n)
    cross_ac = _cross(ac, n)
    num = _sub(_mul(cross_ac, _dot(ab, ab)), _mul(cross_ab, _dot(ac, ac)))
    return _add(p1, _mul(num, 1.0 / denom))


def esfera_por_tres_puntos(
    p1: Vec3, p2: Vec3, p3: Vec3, radio: float
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Esfera de radio `radio` apoyada sobre 3 puntas (centro más alto).

    Devuelve (esfera, None) o (None, motivo). La esfera incluye:
      centro, circuncentro, rho (radio del círculo por las 3 puntas),
      h (distancia del centro al plano) y radio.
    """
    n = _cross(_sub(p2, p1), _sub(p3, p1))
    n_len = _norm(n)
    if n_len < EPS_COLINEAL:
        return None, MOTIVO_COLINEAL

    o = circuncentro_3d(p1, p2, p3)
    if o is None:
        return None, MOTIVO_COLINEAL

    rho = _norm(_sub(o, p1))
    if rho >= radio - 1e-9:
        return None, MOTIVO_RADIO

    h = math.sqrt(radio * radio - rho * rho)
    nn = _mul(n, 1.0 / n_len)
    c_arriba = _add(o, _mul(nn, h))
    c_abajo = _sub(o, _mul(nn, h))
    centro = c_arriba if c_arriba[2] >= c_abajo[2] else c_abajo

    # La esfera "rueda" sobre las puntas: todas deben quedar en su hemisferio inferior.
    if centro[2] < max(p1[2], p2[2], p3[2]) - 1e-9:
        return None, MOTIVO_NO_APOYABLE

    return {
        "centro": centro,
        "circuncentro": o,
        "rho": rho,
        "h": h,
        "radio": radio,
    }, None


def _altura_desde_centros(
    xs: np.ndarray, ys: np.ndarray, centros: Any, radio: float
) -> np.ndarray:
    """Cota de la parte inferior de las esferas indicadas sobre cada (x, y).

    Toma el mínimo entre todas las esferas de `centros`; NaN donde ninguna cubre.
    """
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)
    z = np.full(xs.shape, np.nan, dtype=float)
    c_np = np.asarray(centros, dtype=float).reshape(-1, 3)
    if xs.size == 0 or len(c_np) == 0:
        return z

    r2 = radio * radio
    acumulado = np.full(xs.shape, np.inf, dtype=float)
    for i in range(0, len(c_np), 64):
        blq = c_np[i:i + 64]
        d2 = (xs[None, :] - blq[:, 0:1]) ** 2 + (ys[None, :] - blq[:, 1:2]) ** 2
        vals = np.where(
            d2 <= r2 + 1e-9,
            blq[:, 2:3] - np.sqrt(np.maximum(r2 - d2, 0.0)),
            np.inf,
        )
        acumulado = np.minimum(acumulado, vals.min(axis=0))

    mask = np.isfinite(acumulado)
    z[mask] = acumulado[mask]
    return z


# ============================================================
# PIVOTE SOBRE UNA ARISTA (arco de centros)
# ============================================================

def _punto_arco(m: Vec3, e1: Vec3, e2: Vec3, d: float, ang: float) -> Vec3:
    radial = _add(_mul(e1, math.cos(ang)), _mul(e2, math.sin(ang)))
    return _add(m, _mul(radial, d))


def _trayecto_libre(
    m: Vec3, e1: Vec3, e2: Vec3, d: float, delta: float,
    radio: float, todas: List[Vec3], pasos: int = 13,
) -> bool:
    """True si a lo largo del arco ninguna otra punta queda dentro de la esfera."""
    for k in range(1, pasos + 1):
        p = _punto_arco(m, e1, e2, d, delta * k / pasos)
        if any(math.dist(p, t) < radio - TOL_PUNTA_EN_ESFERA for t in todas):
            return False
    return True


def _arco_de_pivote(
    a: Vec3, b: Vec3, c1: Vec3, c2: Vec3, radio: float, todas: List[Vec3]
) -> Optional[Tuple[Vec3, Vec3, Vec3, float, float]]:
    """Arco de centros de la esfera al pivotar sobre la arista AB.

    Los centros equidistan R de A y B y están sobre una circunferencia en el
    plano perpendicular a AB, centrada en el punto medio. De los dos arcos
    entre c1 y c2 se toma el que pasa más alto y no mete ninguna otra punta
    dentro de la esfera.

    Devuelve (m, e1, e2, d, delta) con centro(t) = m + d*(cos t*e1 + sin t*e2),
    t de 0 (c1) a delta (c2); o None si no hay arco posible.
    """
    m = _mul(_add(a, b), 0.5)
    semi = math.dist(a, b) / 2.0
    d2 = radio * radio - semi * semi
    if d2 <= 1e-12:
        return None
    d = math.sqrt(d2)

    eje_ab = _unit(_sub(b, a))
    r1 = _sub(c1, m)
    n1 = _norm(r1)
    if n1 < 1e-9:
        return None
    e1 = _mul(r1, 1.0 / n1)
    e2 = _unit(_cross(eje_ab, e1))

    r2 = _sub(c2, m)
    theta = math.atan2(_dot(r2, e2), _dot(r2, e1))
    if abs(theta) < 1e-6:
        return None

    candidatos: List[Tuple[float, float]] = []
    for delta in (theta, theta - math.copysign(2.0 * math.pi, theta)):
        if _trayecto_libre(m, e1, e2, d, delta, radio, todas):
            candidatos.append((_punto_arco(m, e1, e2, d, delta / 2.0)[2], delta))

    if not candidatos:
        return None
    delta = max(candidatos)[1]
    return m, e1, e2, d, delta


def _arco_falda(
    a: Vec3, b: Vec3, c1: Vec3, radio: float, saliente: Vec3
) -> Optional[Tuple[Vec3, Vec3, Vec3, float, float]]:
    """Arco de centros al pivotar sobre AB hacia afuera hasta tocar el suelo.

    Parte del centro `c1` de la terna y gira en el sentido que aleja el centro
    del edificio (`saliente`: normal horizontal exterior de la arista) hasta que
    el centro llega a z = R (esfera tangente a z = 0).

    Devuelve (m, e1, e2, d, delta) con el mismo formato que `_arco_de_pivote`.
    """
    m = _mul(_add(a, b), 0.5)
    semi = math.dist(a, b) / 2.0
    d2 = radio * radio - semi * semi
    if d2 <= 1e-12:
        return None
    d = math.sqrt(d2)

    if c1[2] <= radio + TOL_Z:
        return None  # la esfera de la terna ya está a la altura del suelo

    eje_ab = _unit(_sub(b, a))
    r1 = _sub(c1, m)
    n1 = _norm(r1)
    if n1 < 1e-9:
        return None
    e1 = _mul(r1, 1.0 / n1)
    e2 = _unit(_cross(eje_ab, e1))
    if _dot(e2, saliente) < 0.0:
        e2 = _mul(e2, -1.0)  # t > 0 aleja el centro del edificio

    # z(t) = m_z + d * kz * cos(t - fase) = R
    kz = math.hypot(e1[2], e2[2])
    if kz < 1e-9:
        return None
    q = (radio - m[2]) / (d * kz)
    if abs(q) > 1.0:
        return None
    fase = math.atan2(e2[2], e1[2])
    base = math.acos(q)
    dos_pi = 2.0 * math.pi
    delta = min((fase + base) % dos_pi, (fase - base) % dos_pi)
    if delta < 1e-6:
        return None
    return m, e1, e2, d, delta


def _centros_arco(
    arco: Tuple[Vec3, Vec3, Vec3, float, float], c1: Vec3, c2: Vec3
) -> np.ndarray:
    """Posiciones del centro a lo largo del arco (los extremos son c1 y c2)."""
    m, e1, e2, d, delta = arco
    filas = _limitar(math.ceil(math.degrees(abs(delta)) / PASO_ANGULAR_RODADO), FILAS_MIN, FILAS_MAX)
    ang = delta * np.arange(filas + 1) / filas
    centros = np.asarray(m) + d * (
        np.cos(ang)[:, None] * np.asarray(e1) + np.sin(ang)[:, None] * np.asarray(e2)
    )
    centros[0] = c1
    centros[-1] = c2
    return centros


# ============================================================
# MALLAS PARA EL VISOR
# ============================================================

def _subdivisiones_terna(puntas: Tuple[Vec3, Vec3, Vec3]) -> int:
    """Lados por arista de un parche; depende solo de su propia terna."""
    largo = max(math.dist(puntas[i], puntas[(i + 1) % 3]) for i in range(3))
    return _limitar(math.ceil(largo / PASO_TELA), SUBDIV_MIN, SUBDIV_MAX)


def _malla_parche(
    puntas: Tuple[Vec3, Vec3, Vec3], centro: Vec3, radio: float, n: int
) -> Tuple[np.ndarray, List[List[int]]]:
    """Triángulo esférico entre las 3 puntas de la esfera apoyada en ellas."""
    c = np.asarray(centro, dtype=float)
    dirs = np.array([
        (np.asarray(p, dtype=float) - c) / np.linalg.norm(np.asarray(p, dtype=float) - c)
        for p in puntas
    ])

    indice: Dict[Tuple[int, int], int] = {}
    pesos: List[Tuple[float, float, float]] = []
    for i in range(n + 1):
        for j in range(n + 1 - i):
            indice[(i, j)] = len(pesos)
            pesos.append((i / n, j / n, 1.0 - i / n - j / n))

    d = np.asarray(pesos) @ dirs
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    vertices = c + radio * d

    triangulos: List[List[int]] = []
    for i in range(n):
        for j in range(n - i):
            a, b, cc = indice[(i, j)], indice[(i + 1, j)], indice[(i, j + 1)]
            triangulos.append([a, b, cc])
            if j < n - i - 1:
                triangulos.append([b, indice[(i + 1, j + 1)], cc])
    return vertices, triangulos


def _slerp(u: np.ndarray, v: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Interpolación esférica fila a fila entre vectores unitarios: (K, len(t), 3)."""
    w = np.arccos(np.clip(np.sum(u * v, axis=1), -1.0, 1.0))[:, None]
    sw = np.sin(w)
    seguro = sw > 1e-9
    sw_seguro = np.where(seguro, sw, 1.0)
    tt = t[None, :]
    s0 = np.where(seguro, np.sin((1.0 - tt) * w) / sw_seguro, 1.0 - tt)
    s1 = np.where(seguro, np.sin(tt * w) / sw_seguro, tt)
    d = s0[:, :, None] * u[:, None, :] + s1[:, :, None] * v[:, None, :]
    return d / np.linalg.norm(d, axis=2, keepdims=True)


def _malla_banda(
    p: Any, q: Any, centros: np.ndarray, radio: float, n: int,
    colapsa_ini: bool = True, colapsa_fin: bool = True,
) -> Tuple[np.ndarray, List[List[int]]]:
    """Banda: para cada centro, el arco de la esfera entre los puntos P y Q.

    `p` y `q` son un punto fijo o un punto por fila. Si el extremo es fijo para
    todas las esferas (la punta de un mástil), la banda colapsa a un punto ahí
    y se omiten los triángulos de área cero.
    """
    P = np.broadcast_to(np.asarray(p, dtype=float), centros.shape)
    Q = np.broadcast_to(np.asarray(q, dtype=float), centros.shape)
    ua = P - centros
    ua = ua / np.linalg.norm(ua, axis=1, keepdims=True)
    ub = Q - centros
    ub = ub / np.linalg.norm(ub, axis=1, keepdims=True)

    d = _slerp(ua, ub, np.linspace(0.0, 1.0, n + 1))
    vertices = (centros[:, None, :] + radio * d).reshape(-1, 3)

    filas = len(centros) - 1
    ancho = n + 1
    triangulos: List[List[int]] = []
    for k in range(filas):
        for j in range(n):
            p00 = k * ancho + j
            p01 = p00 + 1
            p10 = (k + 1) * ancho + j
            p11 = p10 + 1
            if j > 0 or not colapsa_ini:
                triangulos.append([p00, p10, p01])
            if j < n - 1 or not colapsa_fin:
                triangulos.append([p01, p10, p11])
    return vertices, triangulos


def _malla_union(
    a: Vec3, b: Vec3, centros: np.ndarray, radio: float, n: int
) -> Tuple[np.ndarray, List[List[int]]]:
    """Banda toroidal: el arco AB de la esfera para cada posición del centro."""
    return _malla_banda(a, b, centros, radio, n)


# ============================================================
# TERNAS DE MÁSTILES (esfera vacía, sin Delaunay)
# ============================================================

def _mastiles_unicos(masts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Un mástil por (x, y): si hay varios, el de punta más alta."""
    por_xy: Dict[Tuple[float, float], Dict[str, Any]] = {}
    for m in masts:
        k = _clave_xy(_punta(m))
        previo = por_xy.get(k)
        if previo is None or _punta(m)[2] > _punta(previo)[2]:
            por_xy[k] = m
    return list(por_xy.values())


def _ternas_de_mastiles(masts: List[Dict[str, Any]], radio: float):
    """Todas las ternas cuya esfera de radio R, apoyada en sus 3 puntas, no
    contiene otra punta. Sin Delaunay y sin filtrar por cubierta."""
    ms = _mastiles_unicos(masts)
    n = len(ms)
    if n < 3:
        return []

    puntas = [_punta(m) for m in ms]
    P = np.array(puntas, dtype=float)
    D = np.linalg.norm(P[:, None, :] - P[None, :, :], axis=2)
    idx = np.arange(n)
    # Una terna solo puede existir si sus 3 lados son < 2R
    vecinos = [
        set(int(j) for j in np.nonzero((D[i] < 2.0 * radio) & (idx > i))[0])
        for i in range(n)
    ]

    validas = []  # ((i, j, k), centro)
    for i in range(n):
        for j in sorted(vecinos[i]):
            for k in sorted(vecinos[i] & vecinos[j]):
                esfera, _ = esfera_por_tres_puntos(puntas[i], puntas[j], puntas[k], radio)
                if esfera is None:
                    continue
                dist = np.linalg.norm(P - np.asarray(esfera["centro"]), axis=1)
                dist[[i, j, k]] = np.inf
                if np.any(dist < radio - TOL_PUNTA_EN_ESFERA):
                    continue  # otra punta queda dentro de la esfera
                validas.append(((i, j, k), esfera["centro"]))

    # Ternas con el mismo centro = misma esfera (cuaternas cocirculares):
    # se triangulan en planta solo para no dibujar parches duplicados.
        # Ternas cuyo centro coincide (dentro de TOL_MISMA_ESFERA) = misma esfera
    # (cuaternas cosféricas): se triangulan en planta para no dibujar parches
    # duplicados.
    grupos: List[Dict[str, Any]] = []
    for ijk, c in validas:
        c = np.asarray(c, dtype=float)
        for g in grupos:
            if np.linalg.norm(g["centro"] - c) < TOL_MISMA_ESFERA:
                g["lista"].append(ijk)
                break
        else:
            grupos.append({"centro": c, "lista": [ijk]})

    resultado: List[Tuple[int, int, int]] = []
    for g in grupos:
        lista = g["lista"]
        if len(lista) == 1:
            resultado.append(lista[0])
            continue
        pts_idx = sorted(set().union(*lista))
        pos = {(round(P[i, 0], 4), round(P[i, 1], 4)): i for i in pts_idx}
        for t in triangulate(MultiPoint([(P[i, 0], P[i, 1]) for i in pts_idx])):
            try:
                resultado.append(tuple(
                    pos[(round(x, 4), round(y, 4))] for x, y in list(t.exterior.coords)[:3]
                ))
            except KeyError:
                continue

    ternas = [tuple(ms[i] for i in t) for t in resultado]
    ternas.sort(key=lambda tr: tuple(sorted(str(m.get("id", "")) for m in tr)))
    return ternas


def _ternas_muy_separadas(
    masts: List[Dict[str, Any]], ids_existentes: set, radio: float
):
    """Diagnóstico: triángulos de Delaunay (solo como sugerencia de vecindad) que
    no son terna y fallan únicamente porque los mástiles están muy separados
    (radio de la circunferencia por las 3 puntas >= R). No generan superficie."""
    ms = _mastiles_unicos(masts)
    if len(ms) < 3:
        return []
    por_xy = {_clave_xy(_punta(m)): m for m in ms}

    salida = []
    vistas = set()
    for tri in triangulate(MultiPoint(list(por_xy.keys()))):
        try:
            terna = tuple(
                por_xy[(round(x, 4), round(y, 4))] for x, y in list(tri.exterior.coords)[:3]
            )
        except KeyError:
            continue
        clave = frozenset(str(m.get("id", "")) for m in terna)
        if clave in ids_existentes or clave in vistas:
            continue
        _, motivo = esfera_por_tres_puntos(*(_punta(m) for m in terna), radio)
        if motivo != MOTIVO_RADIO:
            continue
        vistas.add(clave)
        salida.append(terna)
    return salida


def _dentro_triangulo_np(
    xy: Tuple[Tuple[float, float], ...], xs: np.ndarray, ys: np.ndarray
) -> np.ndarray:
    (x1, y1), (x2, y2), (x3, y3) = xy
    det = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
    if abs(det) < 1e-12:
        return np.zeros(xs.shape, dtype=bool)
    l1 = ((y2 - y3) * (xs - x3) + (x3 - x2) * (ys - y3)) / det
    l2 = ((y3 - y1) * (xs - x3) + (x1 - x3) * (ys - y3)) / det
    l3 = 1.0 - l1 - l2
    return (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9)


def _nueva_terna(
    idx: int, terna: Tuple[Dict[str, Any], ...], radio: float, diagnostico: bool = False
) -> Dict[str, Any]:
    puntas = tuple(_punta(m) for m in terna)
    xy = tuple((p[0], p[1]) for p in puntas)
    esfera, motivo = esfera_por_tres_puntos(*puntas, radio)

    rho = esfera["rho"] if esfera is not None else None
    if rho is None and motivo == MOTIVO_RADIO:
        o = circuncentro_3d(*puntas)
        if o is not None:
            rho = _norm(_sub(o, puntas[0]))

    return {
        "idx": idx,
        "ids": [str(m.get("id", "")) for m in terna],
        "puntas": puntas,
        "xy": xy,
        "esfera": esfera,
        "motivo": motivo,
        "rho": rho,
        "id": f"S{idx}" if esfera is not None else f"T{idx}",
        "centros_union": [],  # arcos de pivote de sus aristas (para evaluar)
        "diagnostico": diagnostico,
    }


def _preparar_ternas(
    masts: List[Dict[str, Any]], radio: float
) -> Tuple[List[Dict[str, Any]], List[Vec3]]:
    """Ternas de mástiles con su esfera de radio R (esfera vacía)."""
    todas = [_punta(m) for m in masts]
    ternas = [
        _nueva_terna(idx, terna, radio)
        for idx, terna in enumerate(_ternas_de_mastiles(masts, radio), start=1)
    ]
    return ternas, todas


def _agregar_diagnostico(
    ternas: List[Dict[str, Any]], masts: List[Dict[str, Any]], radio: float,
    sx: np.ndarray, sy: np.ndarray,
) -> None:
    """Agrega las ternas 'mástiles muy separados' que contienen cubierta."""
    if sx.size == 0:
        return
    existentes = {frozenset(t["ids"]) for t in ternas}
    for terna in _ternas_muy_separadas(masts, existentes, radio):
        nueva = _nueva_terna(len(ternas) + 1, terna, radio, diagnostico=True)
        if _dentro_triangulo_np(nueva["xy"], sx, sy).any():
            ternas.append(nueva)


def _filtrar_diagnosticos(
    ternas: List[Dict[str, Any]],
    muestras: List[Dict[str, Any]],
    resultados: List[Tuple[bool, Optional[str], Optional[str]]],
) -> List[Dict[str, Any]]:
    """Conserva el diagnóstico solo donde queda cubierta sin proteger."""
    if not any(t.get("diagnostico") for t in ternas) or not muestras:
        return ternas
    sx = np.array([m["x"] for m in muestras], dtype=float)
    sy = np.array([m["y"] for m in muestras], dtype=float)
    desprotegida = np.array([not r[0] for r in resultados], dtype=bool)

    salida = []
    for t in ternas:
        if t.get("diagnostico"):
            dentro = _dentro_triangulo_np(t["xy"], sx, sy)
            if not np.any(dentro & desprotegida):
                continue
        salida.append(t)
    return salida


def _descartar(terna: Dict[str, Any], motivo: str) -> None:
    """La terna deja de tener superficie: queda como zona a corregir."""
    terna["esfera"] = None
    terna["motivo"] = motivo
    terna["id"] = f"T{terna['idx']}"
    terna.pop("vertices", None)
    terna.pop("triangulos", None)


# ============================================================
# VALIDACIÓN CONTRA SUELO Y CUBIERTA
# ============================================================

def _toca_suelo(vertices: np.ndarray) -> bool:
    return bool(np.min(vertices[:, 2]) <= Z_SUELO)


def _altura_cubierta(
    xs: np.ndarray, ys: np.ndarray,
    regiones: List[Tuple[Polygon, Callable[[float, float], float], str]],
) -> np.ndarray:
    """Cota de la cubierta bajo cada (x, y); NaN donde no hay cubierta."""
    z = np.full(xs.shape, np.nan, dtype=float)
    for poly, z_fn, _rid in regiones:
        minx, miny, maxx, maxy = poly.bounds
        cand = np.nonzero((xs >= minx) & (xs <= maxx) & (ys >= miny) & (ys <= maxy))[0]
        if cand.size == 0:
            continue
        dentro = cand[shapely.intersects_xy(poly, xs[cand], ys[cand])]
        for k in dentro:
            zr = float(z_fn(xs[k], ys[k]))
            if np.isnan(z[k]) or zr > z[k]:
                z[k] = zr
    return z


def _toca_cubierta_union(vertices: np.ndarray, regiones: List[Any], tol: float) -> bool:
    """True si bajo algún punto de la banda la cubierta alcanza su cota."""
    zr = _altura_cubierta(vertices[:, 0], vertices[:, 1], regiones)
    return bool(np.any(np.isfinite(zr) & (zr >= vertices[:, 2] - tol)))


def _toca_cubierta_parche(
    terna: Dict[str, Any], sx: np.ndarray, sy: np.ndarray, sz: np.ndarray, tol: float
) -> bool:
    """True si alguna celda de cubierta del triángulo alcanza la esfera de la terna."""
    if sx.size == 0:
        return False
    dentro = _dentro_triangulo_np(terna["xy"], sx, sy)
    if not dentro.any():
        return False
    e = terna["esfera"]
    z = _altura_desde_centros(sx[dentro], sy[dentro], [e["centro"]], e["radio"])
    return bool(np.any(np.isfinite(z) & (sz[dentro] >= z - tol)))


# ============================================================
# UNIONES ENTRE PARCHES
# ============================================================

def _construir_uniones(
    ternas: List[Dict[str, Any]], todas: List[Vec3], radio: float, regiones: List[Any]
) -> List[Dict[str, Any]]:
    """Una unión por cada par de parches que sobrevivieron y comparten arista."""
    aristas: Dict[Any, List[Tuple[int, int]]] = defaultdict(list)
    for pos, t in enumerate(ternas):
        if t["esfera"] is None:
            continue
        for i in range(3):
            a, b = t["puntas"][i], t["puntas"][(i + 1) % 3]
            aristas[frozenset((_clave_xy(a), _clave_xy(b)))].append((pos, i))

    uniones: List[Dict[str, Any]] = []
    for lista in aristas.values():
        if len(lista) < 2:
            continue  # arista del borde de la malla: no hay con qué unirla
        for (p1, i1), (p2, _i2) in combinations(lista, 2):
            t1, t2 = ternas[p1], ternas[p2]
            a, b = t1["puntas"][i1], t1["puntas"][(i1 + 1) % 3]
            c1, c2 = t1["esfera"]["centro"], t2["esfera"]["centro"]

            if math.dist(c1, c2) < TOL_MISMA_ESFERA:
                continue  # misma esfera: los dos parches ya se tocan sin unión

            union: Dict[str, Any] = {
                "id": f"U{len(uniones) + 1}",
                "mastiles_ids": sorted(set(t1["ids"] + t2["ids"])),
                "ternas_ids": [t1["id"], t2["id"]],
                "a": a,
                "b": b,
                "radio": radio,
                "valida": False,
                "motivo": None,
            }

            arco = _arco_de_pivote(a, b, c1, c2, radio, todas)
            if arco is None:
                union["motivo"] = MOTIVO_UNION
                uniones.append(union)
                continue

            centros = _centros_arco(arco, c1, c2)
            vertices, triangulos = _malla_union(a, b, centros, radio, max(t1["n"], t2["n"]))
            union.update(arco=arco, centros=centros, vertices=vertices, triangulos=triangulos)

            if not np.all(np.isfinite(vertices)):
                union["motivo"] = MOTIVO_UNION
            elif _toca_suelo(vertices):
                union["motivo"] = MOTIVO_TOCA_SUELO
            elif regiones and _toca_cubierta_union(vertices, regiones, TOL_Z):
                union["motivo"] = MOTIVO_TOCA_CUBIERTA
            else:
                union["valida"] = True
                # Los arcos de pivote forman parte de la superficie de las dos ternas.
                t1["centros_union"].append(centros)
                t2["centros_union"].append(centros)
            uniones.append(union)

    return uniones


# ============================================================
# FALDA EXTERIOR (aristas del borde -> suelo) Y CASQUETES DE ESQUINA
# ============================================================

def _huella_edificio(regiones: List[Any]) -> Tuple[Optional[Any], Optional[Any]]:
    """(huella, sólido): la huella es la unión de las cubiertas con las rendijas
    cerradas (sus anillos interiores son los patios); el sólido es la misma
    huella con los patios rellenos."""
    polys = [p for p, _f, _r in regiones]
    if not polys:
        return None, None
    huella = unary_union(polys)
    huella = huella.buffer(CIERRE_RENDIJAS, join_style="mitre").buffer(-CIERRE_RENDIJAS, join_style="mitre")
    if huella.is_empty:
        return None, None
    partes = list(huella.geoms) if hasattr(huella, "geoms") else [huella]
    solido = unary_union([Polygon(p.exterior) for p in partes if p.geom_type == "Polygon"])
    return huella, solido


def _clasificar_borde(
    a: Vec3, b: Vec3, tercero: Vec3, huella: Any, solido: Any
) -> Tuple[str, Tuple[float, float]]:
    """Clasifica una arista del borde de la malla de ternas.

    Sale desde su punto medio hacia afuera (lado opuesto a la 3ª punta de su
    terna) hasta encontrar el borde del techo:
      "exterior": al salir del techo cae fuera de la huella.
      "patio":    al salir del techo cae dentro de un hueco de la huella.
      "interior": el techo continúa (la arista no es borde del edificio).
    Devuelve (clase, normal_horizontal_exterior).
    """
    ex, ey = b[0] - a[0], b[1] - a[1]
    largo = math.hypot(ex, ey)
    if largo < 1e-9:
        return "interior", (0.0, 0.0)
    nx, ny = -ey / largo, ex / largo
    mx, my = (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0
    if (tercero[0] - mx) * nx + (tercero[1] - my) * ny > 0.0:
        nx, ny = -nx, -ny

    pasos = np.arange(PASO_SONDA, ALCANCE_BORDE + 1e-9, PASO_SONDA)
    xs, ys = mx + nx * pasos, my + ny * pasos
    libres = np.nonzero(~shapely.contains_xy(huella, xs, ys))[0]
    if libres.size == 0:
        return "interior", (nx, ny)
    k = libres[0]
    if bool(shapely.contains_xy(solido, xs[k], ys[k])):
        return "patio", (nx, ny)
    return "exterior", (nx, ny)


def _falda_de_arista(
    ternas_t: Dict[str, Any], i: int, normal: Tuple[float, float],
    todas: List[Vec3], radio: float, regiones: List[Any],
) -> Dict[str, Any]:
    """Falda de la arista i de una terna: banda hasta el suelo + triángulo esférico."""
    t = ternas_t
    a, b = t["puntas"][i], t["puntas"][(i + 1) % 3]
    falda: Dict[str, Any] = {
        "tipo": TIPO_FALDA,
        "forma": FORMA_FALDA,
        "mastiles_ids": [t["ids"][i], t["ids"][(i + 1) % 3]],
        "ternas_ids": [t["id"]],
        "puntas": [a, b],
        "normal": normal,
        "radio": radio,
        "valida": False,
        "motivo": None,
    }

    arco = _arco_falda(a, b, t["esfera"]["centro"], radio, (normal[0], normal[1], 0.0))
    if arco is None:
        falda["motivo"] = MOTIVO_FALDA_SUELO
        return falda

    m, e1, e2, d, delta = arco
    if not _trayecto_libre(m, e1, e2, d, delta, radio, todas):
        falda["motivo"] = MOTIVO_FALDA_PUNTA
        return falda

    c_fin = _punto_arco(m, e1, e2, d, delta)
    centros = _centros_arco(arco, t["esfera"]["centro"], c_fin)
    suelo = (c_fin[0], c_fin[1], 0.0)
    n = _limitar(math.ceil(math.dist(a, b) / PASO_TELA), SUBDIV_MIN, SUBDIV_MAX)
    v_banda, t_banda = _malla_union(a, b, centros, radio, n)
    v_tri, t_tri = _malla_parche((a, b, suelo), c_fin, radio, n)
    vertices = np.vstack([v_banda, v_tri])
    triangulos = t_banda + [[x + len(v_banda) for x in tri] for tri in t_tri]

    falda.update(
        centro_fin=c_fin,
        centro_circulo=m,
        radio_circulo=d,
        centros=centros,
        vertices=vertices,
        triangulos=triangulos,
        region=MultiPoint(vertices[:, :2]).convex_hull,
    )
    if not np.all(np.isfinite(vertices)) or np.min(vertices[:, 2]) < -1e-6:
        falda["motivo"] = MOTIVO_FALDA_SUELO
    elif _toca_cubierta_union(vertices, regiones, TOL_Z):
        falda["motivo"] = MOTIVO_FALDA_CUBIERTA
    else:
        falda["valida"] = True
    return falda


def _casquete_de_esquina(
    punta: Vec3, mastil_id: str, f1: Dict[str, Any], f2: Dict[str, Any],
    todas: List[Vec3], radio: float, regiones: List[Any],
) -> Optional[Dict[str, Any]]:
    """Casquete que cierra la esquina entre dos faldas que terminan en un mástil.

    La esfera pivota sobre la punta apoyada en el suelo: su centro recorre la
    circunferencia horizontal (z = R) de radio sqrt(za (2R - za)) alrededor de la
    punta. Cada posición aporta el meridiano de la esfera entre la punta y el
    punto de contacto con el suelo.
    """
    za = punta[2]
    rho = math.sqrt(max(za * (2.0 * radio - za), 0.0))
    if rho < 1e-6:
        return None

    c1, c2 = f1["centro_fin"], f2["centro_fin"]
    th1 = math.atan2(c1[1] - punta[1], c1[0] - punta[0])
    th2 = math.atan2(c2[1] - punta[1], c2[0] - punta[0])
    delta = (th2 - th1 + math.pi) % (2.0 * math.pi) - math.pi
    if abs(delta) < 1e-6:
        return None  # ambas faldas terminan en la misma esfera: no hay esquina
    alterno = delta - math.copysign(2.0 * math.pi, delta)

    # De los dos arcos se toma el que da hacia el exterior de las dos aristas.
    nx = f1["normal"][0] + f2["normal"][0]
    ny = f1["normal"][1] + f2["normal"][1]

    def puntaje(dl: float) -> float:
        ang = th1 + dl / 2.0
        return math.cos(ang) * nx + math.sin(ang) * ny

    dl = max((delta, alterno), key=puntaje)

    filas = _limitar(math.ceil(math.degrees(abs(dl)) / PASO_ANGULAR_RODADO), FILAS_MIN, FILAS_MAX)
    ang = th1 + dl * np.arange(filas + 1) / filas
    centros = np.column_stack([
        punta[0] + rho * np.cos(ang),
        punta[1] + rho * np.sin(ang),
        np.full(filas + 1, radio),
    ])
    centros[0], centros[-1] = c1, c2
    suelo = centros.copy()
    suelo[:, 2] = 0.0

    omega = math.acos(max(-1.0, min(1.0, (radio - za) / radio)))
    n = _limitar(math.ceil(radio * omega / PASO_TELA), SUBDIV_MIN, SUBDIV_MAX)
    vertices, triangulos = _malla_banda(punta, suelo, centros, radio, n, colapsa_fin=False)

    casquete: Dict[str, Any] = {
        "tipo": TIPO_CASQUETE,
        "forma": FORMA_CASQUETE,
        "mastiles_ids": [mastil_id],
        "ternas_ids": sorted(set(f1["ternas_ids"] + f2["ternas_ids"])),
        "puntas": [punta],
        "radio": radio,
        "valida": False,
        "motivo": None,
        "centro_circulo": (punta[0], punta[1], radio),
        "radio_circulo": rho,
        "centros": centros,
        "vertices": vertices,
        "triangulos": triangulos,
        "region": MultiPoint(vertices[:, :2]).convex_hull,
    }

    todas_np = np.asarray(todas, dtype=float).reshape(-1, 3)
    dist = np.linalg.norm(centros[:, None, :] - todas_np[None, :, :], axis=2)
    if not np.all(np.isfinite(vertices)) or np.min(vertices[:, 2]) < -1e-6:
        casquete["motivo"] = MOTIVO_FALDA_SUELO
    elif np.any(dist < radio - TOL_PUNTA_EN_ESFERA):
        casquete["motivo"] = MOTIVO_FALDA_PUNTA
    elif _toca_cubierta_union(vertices, regiones, TOL_Z):
        casquete["motivo"] = MOTIVO_FALDA_CUBIERTA
    else:
        casquete["valida"] = True
    return casquete


def _construir_faldas(
    ternas: List[Dict[str, Any]], todas: List[Vec3], radio: float,
    regiones: List[Any], cota_max: float,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Faldas de las aristas exteriores del borde de la malla y casquetes de esquina.

    Devuelve (faldas, info). `info` informa lo que no se dibujó por regla:
      edificio_alto        cota máxima de cubierta > ALTURA_MAX_FALDA
      omitidas_punta_alta  aristas cuya punta supera 2R
    """
    info: Dict[str, Any] = {
        "edificio_alto": False,
        "omitidas_punta_alta": 0,
        "altura_max_cubierta": cota_max,
    }
    if not regiones:
        return [], info
    if cota_max > ALTURA_MAX_FALDA:
        info["edificio_alto"] = True
        return [], info

    huella, solido = _huella_edificio(regiones)
    if huella is None:
        return [], info

    aristas: Dict[Any, List[Tuple[int, int]]] = defaultdict(list)
    for pos, t in enumerate(ternas):
        if t["esfera"] is None:
            continue
        for i in range(3):
            a, b = t["puntas"][i], t["puntas"][(i + 1) % 3]
            aristas[frozenset((_clave_xy(a), _clave_xy(b)))].append((pos, i))

    faldas: List[Dict[str, Any]] = []
    por_vertice: Dict[Tuple[float, float], List[Dict[str, Any]]] = defaultdict(list)
    for lista in aristas.values():
        if len(lista) != 1:
            continue  # arista compartida: la resuelve una unión
        pos, i = lista[0]
        t = ternas[pos]
        a, b, tercero = t["puntas"][i], t["puntas"][(i + 1) % 3], t["puntas"][(i + 2) % 3]

        clase, normal = _clasificar_borde(a, b, tercero, huella, solido)
        if clase != "exterior":
            continue  # patio o arista interior: sin falda
        if max(a[2], b[2]) > 2.0 * radio - 1e-6:
            info["omitidas_punta_alta"] += 1
            continue

        falda = _falda_de_arista(t, i, normal, todas, radio, regiones)
        falda["id"] = f"F{len(faldas) + 1}"
        faldas.append(falda)
        if falda["valida"]:
            por_vertice[_clave_xy(a)].append(falda)
            por_vertice[_clave_xy(b)].append(falda)

    # Esquinas: un mástil donde terminan exactamente dos faldas válidas.
    punta_por_clave = {_clave_xy(p): p for t in ternas for p in t["puntas"]}
    id_por_clave = {
        _clave_xy(p): t["ids"][k] for t in ternas for k, p in enumerate(t["puntas"])
    }
    nuevos: List[Dict[str, Any]] = []
    for clave, lista in por_vertice.items():
        if len(lista) != 2:
            continue
        casquete = _casquete_de_esquina(
            punta_por_clave[clave], id_por_clave[clave], lista[0], lista[1],
            todas, radio, regiones,
        )
        if casquete is not None:
            nuevos.append(casquete)
    for k, c in enumerate(nuevos, start=1):
        c["id"] = f"C{k}"
    faldas.extend(nuevos)
    return faldas, info


# ============================================================
# CONSTRUCCIÓN DE PARCHES, UNIONES Y FALDAS
# ============================================================

def _construir_superficies(
    masts: List[Dict[str, Any]],
    radio: float,
    subdivisiones: Optional[int],
    muestras: List[Dict[str, Any]],
    regiones: List[Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """Valida cada parche por separado y después cada unión y falda por separado.

    Devuelve (ternas, uniones, faldas, info_faldas). Las ternas descartadas
    quedan con `esfera = None` y su motivo; las uniones y faldas inválidas con
    `valida = False`. Sin cubierta (`regiones` vacío) no se generan faldas.
    """
    ternas, todas = _preparar_ternas(masts, radio)

    sx = np.array([m["x"] for m in muestras], dtype=float)
    sy = np.array([m["y"] for m in muestras], dtype=float)
    sz = np.array([m["z"] for m in muestras], dtype=float)

    for t in ternas:
        n = subdivisiones or _subdivisiones_terna(t["puntas"])
        vertices, triangulos = _malla_parche(t["puntas"], t["esfera"]["centro"], radio, n)
        t.update(n=n, vertices=vertices, triangulos=triangulos)

        if not np.all(np.isfinite(vertices)):
            _descartar(t, MOTIVO_NO_APOYABLE)
        elif _toca_suelo(vertices):
            _descartar(t, MOTIVO_TOCA_SUELO)
        elif _toca_cubierta_parche(t, sx, sy, sz, TOL_Z):
            _descartar(t, MOTIVO_TOCA_CUBIERTA)

    _agregar_diagnostico(ternas, masts, radio, sx, sy)

    uniones = _construir_uniones(ternas, todas, radio, regiones)
    cota_max = float(sz.max()) if sz.size else 0.0
    faldas, info = _construir_faldas(ternas, todas, radio, regiones, cota_max)
    return ternas, uniones, faldas, info


def _resultado_superficies(
    ternas: List[Dict[str, Any]],
    uniones: List[Dict[str, Any]],
    faldas: List[Dict[str, Any]],
    radio: float,
    generar_mallas: bool,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Serializa parches, uniones y faldas válidos y las piezas descartadas."""
    superficies: List[Dict[str, Any]] = []
    sin_esfera: List[Dict[str, Any]] = []
    uniones_sin_superficie: List[Dict[str, Any]] = []

    for t in ternas:
        ids = t["ids"]
        if t["esfera"] is None:
            info = {
                "id": t["id"],
                "tipo": "terna_sin_superficie",
                "mastiles_ids": ids,
                "puntas": [_r3(p) for p in t["puntas"]],
                "motivo": t["motivo"],
                "mensaje": (
                    f"Terna {', '.join(ids)}: {MENSAJES_MOTIVO.get(t['motivo'], 'geometría no válida')}. "
                    "Reubique o agregue mástiles en esta zona."
                ),
                "radio_esfera": radio,
            }
            if t.get("rho") is not None:
                info["radio_circunscrito"] = round(float(t["rho"]), 3)
            sin_esfera.append(info)
            continue

        e = t["esfera"]
        item = {
            "id": t["id"],
            "tipo": "parche",
            "mastiles_ids": ids,
            "puntas": [_r3(p) for p in t["puntas"]],
            "centro_esfera": _r3(e["centro"]),
            "radio": radio,
            "radio_circunscrito": round(e["rho"], 3),
            "altura_centro_sobre_plano": round(e["h"], 3),
            "forma": FORMA_PARCHE,
            "vertices": [],
            "triangulos": [],
        }
        if generar_mallas:
            item["vertices"] = np.round(t["vertices"], 4).tolist()
            item["triangulos"] = t["triangulos"]
        superficies.append(item)

    for u in uniones:
        arista = [_r3(u["a"]), _r3(u["b"])]
        if not u["valida"]:
            uniones_sin_superficie.append({
                "id": u["id"],
                "tipo": TIPO_UNION_SIN,
                "mastiles_ids": u["mastiles_ids"],
                "ternas_ids": u["ternas_ids"],
                "arista": arista,
                "motivo": u["motivo"],
                "mensaje": MENSAJES_MOTIVO.get(u["motivo"], "unión no válida"),
                "radio_esfera": radio,
            })
            continue

        m, _e1, _e2, d, _delta = u["arco"]
        item = {
            "id": u["id"],
            "tipo": "union",
            "mastiles_ids": u["mastiles_ids"],
            "ternas_ids": u["ternas_ids"],
            # Campos que comparten con los parches (el schema los exige):
            # puntas = extremos de la arista, centro_esfera = centro de la
            # circunferencia de pivote, radio_circunscrito = su radio.
            "puntas": arista,
            "centro_esfera": _r3(m),
            "radio": radio,
            "radio_circunscrito": round(float(d), 3),
            "altura_centro_sobre_plano": 0.0,
            "forma": FORMA_UNION,
            # Campos propios de la unión.
            "arista": arista,
            "centros_esfera": np.round(u["centros"], 3).tolist(),
            "vertices": [],
            "triangulos": [],
        }
        if generar_mallas:
            item["vertices"] = np.round(u["vertices"], 4).tolist()
            item["triangulos"] = u["triangulos"]
        superficies.append(item)

    for f in faldas:
        puntas = [_r3(p) for p in f["puntas"]]
        if not f["valida"]:
            uniones_sin_superficie.append({
                "id": f["id"],
                "tipo": TIPO_FALDA_SIN,
                "mastiles_ids": f["mastiles_ids"],
                "ternas_ids": f["ternas_ids"],
                "arista": puntas,
                "motivo": f["motivo"],
                "mensaje": MENSAJES_MOTIVO.get(f["motivo"], "falda no válida"),
                "radio_esfera": radio,
            })
            continue

        item = {
            "id": f["id"],
            "tipo": f["tipo"],
            "mastiles_ids": f["mastiles_ids"],
            "ternas_ids": f["ternas_ids"],
            "puntas": puntas,
            "centro_esfera": _r3(f["centro_circulo"]),
            "radio": radio,
            "radio_circunscrito": round(float(f["radio_circulo"]), 3),
            "altura_centro_sobre_plano": 0.0,
            "forma": f["forma"],
            "arista": puntas,
            "centros_esfera": np.round(f["centros"], 3).tolist(),
            "vertices": [],
            "triangulos": [],
        }
        if generar_mallas:
            item["vertices"] = np.round(f["vertices"], 4).tolist()
            item["triangulos"] = f["triangulos"]
        superficies.append(item)

    return superficies, sin_esfera, uniones_sin_superficie


# ============================================================
# CUBIERTA DEL EDIFICIO (muestreo)
# ============================================================

def _regiones_de_cubierta(
    poligonos: Optional[List[Dict[str, Any]]], building_dim: Dict[str, Any]
) -> List[Tuple[Polygon, Callable[[float, float], float], str]]:
    """Regiones (prismas) de la cubierta: (polígono, función z(x, y), id_prisma).

    El id es el `id` del polígono del Modelo2D, el mismo que llevan los prismas
    del Modelo3D (`prisms[].id`).
    """
    regiones: List[Tuple[Polygon, Callable[[float, float], float], str]] = []
    for i, region in enumerate(poligonos or [], start=1):
        try:
            footprint = normalize_footprint(region)
            if len(footprint) < 3:
                continue
            poly = Polygon(footprint)
            if not poly.is_valid:
                poly = poly.buffer(0)
            if poly.is_empty or poly.area < 1e-6:
                continue
            z_fn, _, _ = top_plane(prepare_region_levels(region))
            rid = str(region.get("id") or f"region_{i}")
            partes = list(poly.geoms) if poly.geom_type == "MultiPolygon" else [poly]
            for p in partes:
                regiones.append((p, z_fn, rid))
        except (ValueError, TypeError):
            continue

    if not regiones:
        # Fallback (compatibilidad): rectángulo longitud x anchura a la altura H.
        largo = float(building_dim.get("longitud", 20.0))
        ancho = float(building_dim.get("anchura", 15.0))
        alto = float(building_dim.get("altura", 7.5))
        regiones.append((box(0.0, 0.0, largo, ancho), lambda x, y, z=alto: z, "cubierta"))
    return regiones


def _muestrear_cubierta(
    regiones: List[Tuple[Polygon, Callable[[float, float], float], str]], paso: float
) -> Tuple[List[Dict[str, Any]], float]:
    """Divide cada región en celdas de `paso` m; cada celda es una muestra."""
    area_total = sum(r[0].area for r in regiones)
    paso = max(paso, math.sqrt(area_total / MAX_MUESTRAS)) if area_total > 0 else paso

    muestras: List[Dict[str, Any]] = []
    for r_idx, (poly, z_fn, _rid) in enumerate(regiones):
        minx, miny, maxx, maxy = poly.bounds
        nx = max(1, math.ceil((maxx - minx) / paso))
        ny = max(1, math.ceil((maxy - miny) / paso))
        for ix in range(nx):
            for iy in range(ny):
                celda = box(
                    minx + ix * paso, miny + iy * paso,
                    minx + (ix + 1) * paso, miny + (iy + 1) * paso,
                )
                if not celda.intersects(poly):
                    continue
                pieza = celda.intersection(poly)
                if pieza.is_empty or pieza.area < 1e-6:
                    continue
                c = pieza.centroid
                if not pieza.covers(c):
                    c = pieza.representative_point()
                muestras.append({
                    "region": r_idx,
                    "pieza": pieza,
                    "x": c.x,
                    "y": c.y,
                    "z": float(z_fn(c.x, c.y)),
                })
    return muestras, paso


def _evaluar_muestras(
    muestras: List[Dict[str, Any]],
    ternas: List[Dict[str, Any]],
    faldas: List[Dict[str, Any]],
    radio: float,
) -> List[Tuple[bool, Optional[str], Optional[str]]]:
    """Para cada celda: (protegida, motivo_si_no, id_de_la_superficie).

    - Celda dentro de una terna con superficie: queda protegida si la cubierta
      está por debajo de esa superficie (esfera de la terna + filetes de sus
      aristas); si no, `sobre_la_esfera`.
    - Celda dentro de la huella de una falda o casquete válido: queda protegida
      si la cubierta está por debajo de esa superficie.
    - Celda dentro de una terna descartada: el motivo de esa terna
      (muy separados, toca suelo, toca cubierta...).
    - Celda fuera de toda terna y falda: `fuera_de_triangulacion`.
    """
    total = len(muestras)
    if total == 0:
        return []

    sx = np.array([m["x"] for m in muestras], dtype=float)
    sy = np.array([m["y"] for m in muestras], dtype=float)
    sz = np.array([m["z"] for m in muestras], dtype=float)

    protegida = np.zeros(total, dtype=bool)
    dentro_valida = np.zeros(total, dtype=bool)
    superficie: List[Optional[str]] = [None] * total
    motivo_descartada: List[Optional[str]] = [None] * total

    for t in ternas:
        idx = np.nonzero(_dentro_triangulo_np(t["xy"], sx, sy))[0]
        if idx.size == 0:
            continue

        if t["esfera"] is None:
            for i in idx:
                if motivo_descartada[i] is None:
                    motivo_descartada[i] = t["motivo"]
            continue

        dentro_valida[idx] = True
        centros = [t["esfera"]["centro"]] + list(t["centros_union"])
        centros_np = np.vstack([np.asarray(c, dtype=float).reshape(-1, 3) for c in centros])
        z = _altura_desde_centros(sx[idx], sy[idx], centros_np, radio)
        ok = np.isfinite(z) & (sz[idx] <= z + TOL_Z)
        for i in idx[ok & ~protegida[idx]]:
            protegida[i] = True
            superficie[i] = t["id"]

    for f in faldas:
        if not f["valida"]:
            continue
        idx = np.nonzero(shapely.intersects_xy(f["region"], sx, sy))[0]
        if idx.size == 0:
            continue
        dentro_valida[idx] = True
        z = _altura_desde_centros(sx[idx], sy[idx], f["centros"], radio)
        ok = np.isfinite(z) & (sz[idx] <= z + TOL_Z)
        for i in idx[ok & ~protegida[idx]]:
            protegida[i] = True
            superficie[i] = f["id"]

    resultados: List[Tuple[bool, Optional[str], Optional[str]]] = []
    for i in range(total):
        if protegida[i]:
            resultados.append((True, None, superficie[i]))
        elif motivo_descartada[i] is not None:
            resultados.append((False, motivo_descartada[i], None))
        elif dentro_valida[i]:
            resultados.append((False, MOTIVO_SOBRE, None))
        else:
            resultados.append((False, MOTIVO_FUERA, None))
    return resultados


def _poligono_a_3d(coords, z_fn) -> List[List[float]]:
    return [
        [round(x, 3), round(y, 3), round(float(z_fn(x, y)), 3)]
        for x, y in list(coords)[:-1]
    ]


# ============================================================
# SERVICIO
# ============================================================

class SPDAService:
    """Servicio de evaluación SPDA con parches, uniones y faldas independientes."""

    @staticmethod
    def generar_superficies_esfera(
        masts: List[Dict[str, Any]],
        rolling_sphere_radius: float,
        generar_mallas: bool = True,
        forma_superficie: str = FORMA_PARCHE,
        subdivisiones: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Solo geometría: parches, uniones y piezas descartadas.

        Sin cubierta, solo se controla el contacto con el suelo, y no se generan
        faldas (necesitan la huella del edificio) ni diagnóstico de mástiles
        separados (necesita celdas de cubierta).
        `forma_superficie` se mantiene por compatibilidad y no se usa.
        """
        radio = float(rolling_sphere_radius)
        ternas, uniones, faldas, _info = _construir_superficies(masts, radio, subdivisiones, [], [])
        superficies, sin_esfera, uniones_sin = _resultado_superficies(
            ternas, uniones, faldas, radio, generar_mallas
        )
        return {
            "superficies_esfera": superficies,
            "triangulos_sin_esfera": sin_esfera,
            "uniones_sin_superficie": uniones_sin,
        }

    @staticmethod
    def evaluate_masts_coverage(
        masts: List[Dict[str, Any]],
        building_dim: Dict[str, Any],
        rolling_sphere_radius: float,
        poligonos: Optional[List[Dict[str, Any]]] = None,
        paso_malla: float = 1.0,
        generar_mallas: bool = True,
        forma_superficie: str = FORMA_PARCHE,
        subdivisiones: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Evalúa la cobertura de la cubierta con parches, uniones y faldas.

        - `poligonos`: polígonos del Modelo2D (cubiertas con sus niveles). Si no
          se pasan, se usa el rectángulo `building_dim` (comportamiento previo).
        - `forma_superficie`: se mantiene por compatibilidad (se ignora).
        - `subdivisiones`: lados por arista de cada parche; por defecto se
          calcula por terna según el largo de sus aristas.
        """
        radio = float(rolling_sphere_radius)

        regiones = _regiones_de_cubierta(poligonos, building_dim)
        muestras, paso_usado = _muestrear_cubierta(regiones, paso_malla)

        ternas, uniones, faldas, info_faldas = _construir_superficies(
            masts, radio, subdivisiones, muestras, regiones
        )
        resultados = _evaluar_muestras(muestras, ternas, faldas, radio)
        ternas = _filtrar_diagnosticos(ternas, muestras, resultados)
        superficies, sin_esfera, uniones_sin = _resultado_superficies(
            ternas, uniones, faldas, radio, generar_mallas
        )

        puntos_cobertura: List[Dict[str, Any]] = []
        puntos_desprotegidos: List[Dict[str, Any]] = []
        area_total = 0.0
        area_protegida = 0.0
        piezas_libres: Dict[Tuple[int, str], List[Any]] = defaultdict(list)
        por_prisma: Dict[str, Dict[str, float]] = {}
        for _poly, _fn, rid in regiones:
            por_prisma.setdefault(rid, {"area": 0.0, "prot": 0.0})

        puntas_xy = [
            (
                float(m.get("posicion_x", 0.0)),
                float(m.get("posicion_y", 0.0)),
                str(m.get("id", "")),
            )
            for m in masts
        ]

        for m, (protegido, motivo, sid) in zip(muestras, resultados):
            area = m["pieza"].area
            area_total += area
            acum = por_prisma[regiones[m["region"]][2]]
            acum["area"] += area

            dist_min, mastil_cercano = float("inf"), None
            for mx, my, mid in puntas_xy:
                d = math.hypot(m["x"] - mx, m["y"] - my)
                if d < dist_min:
                    dist_min, mastil_cercano = d, mid

            item = {
                "x": round(m["x"], 3),
                "y": round(m["y"], 3),
                "z": round(m["z"], 3),
                "protegido": protegido,
                "distancia_minima_mastil": round(dist_min, 2) if puntas_xy else None,
                "mastil_cobertura_id": mastil_cercano if protegido else None,
                "superficie_id": sid,
                "motivo": motivo,
            }
            if protegido:
                area_protegida += area
                acum["prot"] += area
                puntos_cobertura.append(item)
            else:
                puntos_desprotegidos.append(item)
                piezas_libres[(m["region"], motivo)].append(m["pieza"])

        # Zonas desprotegidas como polígonos 3D (para resaltarlas en el visor).
        zonas: List[Dict[str, Any]] = []
        for (r_idx, motivo), piezas in piezas_libres.items():
            z_fn = regiones[r_idx][1]
            union = unary_union(piezas)
            partes = list(union.geoms) if hasattr(union, "geoms") else [union]
            for parte in partes:
                if parte.geom_type != "Polygon" or parte.area < 1e-6:
                    continue
                parte = parte.simplify(0.01, preserve_topology=True)
                c = (
                    parte.representative_point()
                    if not parte.contains(parte.centroid)
                    else parte.centroid
                )
                zonas.append({
                    "id_prisma": regiones[r_idx][2],
                    "motivo": motivo,
                    "mensaje": MENSAJES_MOTIVO.get(motivo, ""),
                    "area_m2": round(parte.area, 2),
                    "centroide": {
                        "x": round(c.x, 3),
                        "y": round(c.y, 3),
                        "z": round(float(z_fn(c.x, c.y)), 3),
                    },
                    "poligono": _poligono_a_3d(parte.exterior.coords, z_fn),
                    "huecos": [_poligono_a_3d(h.coords, z_fn) for h in parte.interiors],
                })
        zonas.sort(key=lambda z: z["area_m2"], reverse=True)
        for i, z in enumerate(zonas, start=1):
            z["id"] = f"Z{i}"

        porcentaje = round(area_protegida / area_total * 100.0, 2) if area_total > 0 else 0.0

        prismas: List[Dict[str, Any]] = []
        for rid, a in por_prisma.items():
            if a["area"] <= 0:
                continue
            if a["prot"] >= a["area"] - 1e-6:
                estado = "protegido"
            elif a["prot"] <= 1e-9:
                estado = "desprotegido"
            else:
                estado = "parcial"
            prismas.append({
                "id": rid,
                "area_m2": round(a["area"], 2),
                "area_protegida_m2": round(a["prot"], 2),
                "porcentaje_cobertura": round(a["prot"] / a["area"] * 100.0, 2),
                "estado": estado,
            })

        advertencias: List[str] = []
        if not masts:
            advertencias.append("No se ha colocado ningún mástil captor en la estructura.")
        elif not ternas:
            advertencias.append(
                "Se necesitan al menos 3 mástiles no alineados para formar una terna y calcular la esfera rodante."
            )
        if sin_esfera:
            detalle = "; ".join(
                f"{n} por {ETIQUETAS_MOTIVO.get(mt, mt)}"
                for mt, n in Counter(t["motivo"] for t in sin_esfera).items()
            )
            advertencias.append(
                f"{len(sin_esfera)} terna(s) sin superficie con R = {radio:g} m ({detalle}). "
                "Reubique los mástiles indicados en 'ternas sin esfera posible'."
            )
        uniones_fallidas = [u for u in uniones_sin if u["tipo"] == TIPO_UNION_SIN]
        faldas_fallidas = [u for u in uniones_sin if u["tipo"] == TIPO_FALDA_SIN]
        if uniones_fallidas:
            detalle = "; ".join(
                f"{n} por {ETIQUETAS_MOTIVO.get(mt, mt)}"
                for mt, n in Counter(u["motivo"] for u in uniones_fallidas).items()
            )
            advertencias.append(
                f"{len(uniones_fallidas)} unión(es) entre ternas sin superficie ({detalle})."
            )
        if faldas_fallidas:
            detalle = "; ".join(
                f"{n} por {ETIQUETAS_MOTIVO.get(mt, mt)}"
                for mt, n in Counter(u["motivo"] for u in faldas_fallidas).items()
            )
            advertencias.append(
                f"{len(faldas_fallidas)} falda(s) o esquina(s) del borde sin superficie ({detalle}). "
                "Revise los mástiles del borde y las cubiertas más bajas contiguas."
            )
        if info_faldas["edificio_alto"]:
            advertencias.append(
                "No se dibuja la falda del edificio: la cubierta llega a "
                f"{info_faldas['altura_max_cubierta']:.1f} m (más de {ALTURA_MAX_FALDA:g} m) "
                "y se necesita protección en los laterales."
            )
        elif info_faldas["omitidas_punta_alta"]:
            advertencias.append(
                f"{info_faldas['omitidas_punta_alta']} arista(s) del borde sin falda: la punta del mástil "
                f"supera 2R = {2 * radio:g} m y la esfera no puede tocar la punta y el suelo a la vez."
            )
        if masts and porcentaje < 100.0:
            advertencias.append(
                f"La cobertura es del {porcentaje}%. Hay {len(zonas)} zona(s) desprotegida(s) "
                f"({round(area_total - area_protegida, 2)} m²) que requieren ajustar la posición de los mástiles."
            )

        return {
            "radio_esfera_rodante_r": radio,
            "total_mastiles": len(masts),
            "superficies_esfera": superficies,
            "triangulos_sin_esfera": sin_esfera,
            "uniones_sin_superficie": uniones_sin,
            "zonas_desprotegidas": zonas,
            "prismas": prismas,
            "puntos_cobertura": puntos_cobertura,
            "puntos_desprotegidos": puntos_desprotegidos,
            "porcentaje_cobertura": porcentaje,
            "area_total_m2": round(area_total, 2),
            "area_protegida_m2": round(area_protegida, 2),
            "paso_malla_m": round(paso_usado, 3),
            "advertencias": advertencias,
        }

    @staticmethod
    def resumen_para_persistencia(
        evaluacion: Dict[str, Any], incluir_malla: bool = False
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Arma (zonas_protegidas, zonas_vulnerables, mallas_cobertura) para `resultado_simulacion`.

        - zonas_protegidas: prismas cubiertos al 100 %.
        - zonas_vulnerables: prismas con alguna parte sin cobertura, con sus
          zonas (polígonos 3D) y el motivo de cada una.
        - mallas_cobertura: parches, uniones, faldas y piezas sin superficie. Por
          defecto sin vértices/triángulos (se regeneran con los mástiles y R);
          `incluir_malla=True` los guarda también.
        """
        zonas_por_prisma: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for z in evaluacion.get("zonas_desprotegidas", []):
            zonas_por_prisma[z.get("id_prisma")].append(
                {k: z.get(k) for k in ("id", "motivo", "area_m2", "centroide", "poligono", "huecos")}
            )

        protegidas: List[Dict[str, Any]] = []
        vulnerables: List[Dict[str, Any]] = []
        for p in evaluacion.get("prismas", []):
            if p["estado"] == "protegido":
                protegidas.append({
                    "id_prisma": p["id"],
                    "area_m2": p["area_m2"],
                    "porcentaje_cobertura": p["porcentaje_cobertura"],
                })
            else:
                vulnerables.append({
                    "id_prisma": p["id"],
                    "estado": p["estado"],
                    "area_m2": p["area_m2"],
                    "area_desprotegida_m2": round(p["area_m2"] - p["area_protegida_m2"], 2),
                    "porcentaje_cobertura": p["porcentaje_cobertura"],
                    "zonas": zonas_por_prisma.get(p["id"], []),
                })

        mallas: List[Dict[str, Any]] = []
        for s in evaluacion.get("superficies_esfera", []):
            item = {
                "tipo": s.get("tipo", "parche"),
                **{k: v for k, v in s.items() if k not in ("vertices", "triangulos", "tipo")},
            }
            if incluir_malla:
                item["vertices"], item["triangulos"] = s.get("vertices", []), s.get("triangulos", [])
            mallas.append(item)
        for t in evaluacion.get("triangulos_sin_esfera", []):
            mallas.append({"tipo": "terna_sin_superficie", **{k: v for k, v in t.items() if k != "tipo"}})
        for u in evaluacion.get("uniones_sin_superficie", []):
            mallas.append({"tipo": u.get("tipo", TIPO_UNION_SIN), **{k: v for k, v in u.items() if k != "tipo"}})

        return protegidas, vulnerables, mallas