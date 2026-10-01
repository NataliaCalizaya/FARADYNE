"""
app.services.spda_service

Servicio de evaluación de cobertura SPDA (HU05) por el Método de la Esfera
Rodante, reformulado "por ternas de mástiles":

1. Se triangula (Delaunay en planta) el conjunto de mástiles del proyecto.
2. Para cada triángulo (3 puntas de mástil) se calcula la posición de la
   esfera rodante de radio R que se apoya en las 3 puntas (misma matemática
   que ESFERA3P.lsp: circuncentro 3D + desplazamiento h sobre la normal y
   elección del centro más alto).
3. Se conserva solo el casquete inferior de la esfera (la parte que queda por
   debajo del plano de las 3 puntas). La unión de estos casquetes da la
   ilusión de una malla continua sobre el edificio, pero en realidad son
   superficies independientes, una por terna.
4. Si para una terna no existe esfera (radio insuficiente, puntas colineales o
   esfera no apoyable), esa zona queda marcada como NO cubrible y debe
   corregirla el usuario moviendo/agregando mástiles.
5. Se muestrea la cubierta del edificio (polígonos del Modelo2D) y cada celda
   se marca como protegida si queda por debajo de algún casquete.

Convención de coordenadas: todo se devuelve en el sistema del Modelo2D/3D
(x, y = planta en metros; z = altura). En el visor (three.js, Y hacia arriba)
el punto se dibuja como (x, z, y), igual que la cámara de `vista_defecto`.
"""

import math
from collections import Counter, defaultdict
from typing import Any, Callable, Dict, List, Optional, Tuple

from shapely.geometry import MultiPoint, Point, Polygon, box
from shapely.ops import triangulate, unary_union

from app.services.model3d_generator_service import (
    normalize_footprint,
    prepare_region_levels,
    top_plane,
)

Vec3 = Tuple[float, float, float]

EPS_COLINEAL = 1e-6      # |n| mínimo (m²) para considerar 3 puntas no colineales
TOL_Z = 0.05             # margen de 5 cm, igual que la versión anterior
MAX_MUESTRAS = 6000      # tope de celdas de cubierta a evaluar

MOTIVO_RADIO = "sin_esfera_radio_insuficiente"
MOTIVO_COLINEAL = "sin_esfera_puntas_colineales"
MOTIVO_NO_APOYABLE = "sin_esfera_no_apoyable"
MOTIVO_FUERA = "fuera_de_triangulacion"
MOTIVO_SOBRE = "sobre_la_esfera"

MENSAJES_MOTIVO = {
    MOTIVO_RADIO: "el radio de la esfera no alcanza a tocar las 3 puntas (mástiles muy separados)",
    MOTIVO_COLINEAL: "las 3 puntas están alineadas",
    MOTIVO_NO_APOYABLE: "la esfera no puede apoyarse sobre las 3 puntas (diferencia de alturas excesiva)",
    MOTIVO_FUERA: "zona fuera de cualquier terna de mástiles",
    MOTIVO_SOBRE: "la cubierta queda por encima de la esfera",
}


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


def _r3(v: Vec3) -> List[float]:
    return [round(v[0], 3), round(v[1], 3), round(v[2], 3)]


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
      h (distancia del centro al plano) y eje (unitario, centro -> plano).
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
    if c_arriba[2] >= c_abajo[2]:
        centro, signo = c_arriba, 1.0
    else:
        centro, signo = c_abajo, -1.0

    # La esfera "rueda" sobre las puntas: todas deben quedar en su hemisferio inferior.
    if centro[2] < max(p1[2], p2[2], p3[2]) - 1e-9:
        return None, MOTIVO_NO_APOYABLE

    return {
        "centro": centro,
        "circuncentro": o,
        "rho": rho,
        "h": h,
        "eje": _mul(nn, -signo),  # de centro hacia el plano (y más allá: casquete)
        "radio": radio,
    }, None


def _z_casquete(esfera: Dict[str, Any], x: float, y: float) -> Optional[float]:
    """Cota Z de la parte inferior de la esfera sobre el punto (x, y)."""
    cx, cy, cz = esfera["centro"]
    r = esfera["radio"]
    d2 = (x - cx) ** 2 + (y - cy) ** 2
    if d2 > r * r:
        return None
    return cz - math.sqrt(r * r - d2)


# ============================================================
# MALLAS DEL CASQUETE (para el visor 3D)
# ============================================================

# def _malla_triangulo(
#     puntas: Tuple[Vec3, Vec3, Vec3], esfera: Dict[str, Any], n: int
# ) -> Tuple[List[List[float]], List[List[int]]]:
#     """Casquete inferior recortado al triángulo de las 3 puntas (en planta).

#     Teselado baricéntrico del triángulo; cada vértice se lleva a la cota Z de
#     la esfera. Las 3 esquinas coinciden exactamente con las puntas y los
#     triángulos vecinos comparten arista sin solaparse (efecto "malla").
#     """
#     (x1, y1, _), (x2, y2, _), (x3, y3, _) = puntas
#     indice: Dict[Tuple[int, int], int] = {}
#     vertices: List[List[float]] = []
#     for i in range(n + 1):
#         for j in range(n + 1 - i):
#             u, v = i / n, j / n
#             w = 1.0 - u - v
#             x = u * x1 + v * x2 + w * x3
#             y = u * y1 + v * y2 + w * y3
#             cx, cy, cz = esfera["centro"]
#             rad = max(0.0, esfera["radio"] ** 2 - (x - cx) ** 2 - (y - cy) ** 2)
#             z = cz - math.sqrt(rad)
#             indice[(i, j)] = len(vertices)
#             vertices.append([round(x, 3), round(y, 3), round(z, 3)])

#     triangulos: List[List[int]] = []
#     for i in range(n):
#         for j in range(n - i):
#             triangulos.append([indice[(i, j)], indice[(i + 1, j)], indice[(i, j + 1)]])
#             if j < n - i - 1:
#                 triangulos.append(
#                     [indice[(i + 1, j)], indice[(i + 1, j + 1)], indice[(i, j + 1)]]
#                 )
#     return vertices, triangulos
def _malla_superficie_esferica(
    puntas: Tuple[Vec3, Vec3, Vec3],
    esfera: Dict[str, Any],
    n: int = 24,
) -> Tuple[List[List[float]], List[List[int]]]:

    p1, p2, p3 = puntas
    centro = esfera["centro"]
    radio = float(esfera["radio"])

    v1 = _unit(_sub(p1, centro))
    v2 = _unit(_sub(p2, centro))
    v3 = _unit(_sub(p3, centro))

    indice: Dict[Tuple[int, int], int] = {}
    vertices: List[List[float]] = []
    triangulos: List[List[int]] = []

    for i in range(n + 1):
        for j in range(n + 1 - i):

            u = i / n
            v = j / n
            w = 1.0 - u - v

            direccion = (
                v1[0] * u + v2[0] * v + v3[0] * w,
                v1[1] * u + v2[1] * v + v3[1] * w,
                v1[2] * u + v2[2] * v + v3[2] * w,
            )

            direccion = _unit(direccion)

            punto = _add(
                centro,
                _mul(direccion, radio),
            )

            indice[(i, j)] = len(vertices)
            vertices.append(_r3(punto))

    for i in range(n):
        for j in range(n - i):

            a = indice[(i, j)]
            b = indice[(i + 1, j)]
            c = indice[(i, j + 1)]

            triangulos.append([a, b, c])

            if j < n - i - 1:
                d = indice[(i + 1, j + 1)]
                triangulos.append([b, d, c])

    return vertices, triangulos

    # ------------------------------------------------------------
    # TRIANGULACIÓN
    # ------------------------------------------------------------

    for i in range(n):

        for j in range(n - i):

            a = indice[(i, j)]
            b = indice[(i + 1, j)]
            c = indice[(i, j + 1)]

            triangulos.append([a, b, c])

            if j < n - i - 1:

                d = indice[(i + 1, j + 1)]

                triangulos.append([b, d, c])

    return vertices, triangulos


# ============================================================
# TRIANGULACIÓN DE MÁSTILES
# ============================================================

def _punta(m: Dict[str, Any]) -> Vec3:
    return (
        float(m.get("posicion_x", 0.0)),
        float(m.get("posicion_y", 0.0)),
        float(m.get("posicion_z", 0.0)) + float(m.get("altura", 0.0)),
    )


def _ternas_de_mastiles(masts: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], ...]]:
    """Delaunay en planta -> ternas de mástiles vecinos."""
    por_xy: Dict[Tuple[float, float], Dict[str, Any]] = {}
    for m in masts:
        clave = (round(float(m.get("posicion_x", 0.0)), 4), round(float(m.get("posicion_y", 0.0)), 4))
        previo = por_xy.get(clave)
        if previo is None or _punta(m)[2] > _punta(previo)[2]:
            por_xy[clave] = m  # dos mástiles en el mismo XY: vale el más alto

    if len(por_xy) < 3:
        return []

    triangulos = triangulate(MultiPoint(list(por_xy.keys())))
    ternas = []
    for t in triangulos:
        coords = list(t.exterior.coords)[:3]
        try:
            ternas.append(tuple(por_xy[(round(x, 4), round(y, 4))] for x, y in coords))
        except KeyError:
            continue
    ternas.sort(key=lambda tr: tuple(sorted(str(m.get("id", "")) for m in tr)))
    return ternas


def _dentro_triangulo(tri: Dict[str, Any], px: float, py: float) -> bool:
    (x1, y1), (x2, y2), (x3, y3) = tri["xy"]
    det = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
    if abs(det) < 1e-12:
        return False
    l1 = ((y2 - y3) * (px - x3) + (x3 - x2) * (py - y3)) / det
    l2 = ((y3 - y1) * (px - x3) + (x1 - x3) * (py - y3)) / det
    l3 = 1.0 - l1 - l2
    return min(l1, l2, l3) >= -1e-9


def _construir_superficies(
    masts: List[Dict[str, Any]],
    radio: float,
    generar_mallas: bool,
    forma: str,
    subdivisiones: Optional[int],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Devuelve (superficies, ternas_sin_esfera, ternas_para_evaluar)."""
    superficies: List[Dict[str, Any]] = []
    sin_esfera: List[Dict[str, Any]] = []
    evaluables: List[Dict[str, Any]] = []

    for idx, terna in enumerate(_ternas_de_mastiles(masts), start=1):
        puntas = tuple(_punta(m) for m in terna)
        ids = [str(m.get("id", "")) for m in terna]
        xy = tuple((p[0], p[1]) for p in puntas)
        registro = {
            "xy": xy,
            "bbox": (min(p[0] for p in xy), min(p[1] for p in xy),
                     max(p[0] for p in xy), max(p[1] for p in xy)),
        }

        esfera, motivo = esfera_por_tres_puntos(*puntas, radio)
        if esfera is None:
            registro.update({"esfera": None, "motivo": motivo, "id": f"T{idx}"})
            evaluables.append(registro)
            info = {
                "id": f"T{idx}",
                "mastiles_ids": ids,
                "puntas": [_r3(p) for p in puntas],
                "motivo": motivo,
                "mensaje": (
                    f"Terna {', '.join(ids)}: {MENSAJES_MOTIVO[motivo]}. "
                    "Reubique o agregue mástiles en esta zona."
                ),
                "radio_esfera": radio,
            }
            if motivo == MOTIVO_RADIO:
                info["radio_circunscrito"] = round(_norm(_sub(circuncentro_3d(*puntas), puntas[0])), 3)
            sin_esfera.append(info)
            continue

        sid = f"S{idx}"
        registro.update({"esfera": esfera, "motivo": None, "id": sid, "ids": ids})
        evaluables.append(registro)

        item = {
            "id": sid,
            "mastiles_ids": ids,
            "puntas": [_r3(p) for p in puntas],
            "centro_esfera": _r3(esfera["centro"]),
            "radio": radio,
            "radio_circunscrito": round(esfera["rho"], 3),
            "altura_centro_sobre_plano": round(esfera["h"], 3),
            "forma": forma,
            "vertices": [],
            "triangulos": [],
        }
        if generar_mallas:
            lado_max = max(
                math.dist(xy[0], xy[1]),
                math.dist(xy[1], xy[2]),
                math.dist(xy[2], xy[0]),
            )
            # Más subdivisiones = superficie más suave.
            n = subdivisiones or max(4,min(16, math.ceil(lado_max / 2.0)),
            )
            item["vertices"], item["triangulos"] = _malla_superficie_esferica(
                puntas,
                esfera,
                n,
            )
    return superficies, sin_esfera, evaluables


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
                celda = box(minx + ix * paso, miny + iy * paso,
                            minx + (ix + 1) * paso, miny + (iy + 1) * paso)
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


def _evaluar_muestra(m: Dict[str, Any], evaluables: List[Dict[str, Any]]) -> Tuple[bool, Optional[str], Optional[str]]:
    """Devuelve (protegido, motivo_si_no, id_superficie)."""
    px, py, pz = m["x"], m["y"], m["z"]
    motivo_invalida: Optional[str] = None
    dentro_valida = False

    for tri in evaluables:
        bx0, by0, bx1, by1 = tri["bbox"]
        if px < bx0 - 1e-9 or px > bx1 + 1e-9 or py < by0 - 1e-9 or py > by1 + 1e-9:
            continue
        if not _dentro_triangulo(tri, px, py):
            continue
        if tri["esfera"] is None:
            motivo_invalida = motivo_invalida or tri["motivo"]
            continue
        dentro_valida = True
        z_esf = _z_casquete(tri["esfera"], px, py)
        if z_esf is not None and pz <= z_esf + TOL_Z:
            return True, None, tri["id"]

    if motivo_invalida:
        return False, motivo_invalida, None
    if dentro_valida:
        return False, MOTIVO_SOBRE, None
    return False, MOTIVO_FUERA, None


def _poligono_a_3d(coords, z_fn) -> List[List[float]]:
    return [[round(x, 3), round(y, 3), round(float(z_fn(x, y)), 3)] for x, y in list(coords)[:-1]]


# ============================================================
# SERVICIO
# ============================================================

class SPDAService:
    """Servicio de evaluación de cobertura de mástiles (HU05)."""

    @staticmethod
    def generar_superficies_esfera(
        masts: List[Dict[str, Any]],
        rolling_sphere_radius: float,
        generar_mallas: bool = True,
        forma_superficie: str = "triangulo",
        subdivisiones: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Solo geometría: superficies por terna y ternas sin esfera posible."""
        superficies, sin_esfera, _ = _construir_superficies(
            masts, rolling_sphere_radius, generar_mallas, forma_superficie, subdivisiones
        )
        return {"superficies_esfera": superficies, "triangulos_sin_esfera": sin_esfera}

    @staticmethod
    def evaluate_masts_coverage(
        masts: List[Dict[str, Any]],
        building_dim: Dict[str, Any],
        rolling_sphere_radius: float = 30.0,
        poligonos: Optional[List[Dict[str, Any]]] = None,
        paso_malla: float = 1.0,
        generar_mallas: bool = True,
        forma_superficie: str = "triangulo",
        subdivisiones: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Evalúa la cobertura de la cubierta con esferas apoyadas en ternas de mástiles.

        - `poligonos`: polígonos del Modelo2D (cubiertas con sus niveles). Si no
          se pasan, se usa el rectángulo `building_dim` (comportamiento previo).
        - `forma_superficie`: "triangulo" (casquete recortado a la terna, forma
          malla continua) o "casquete" (esfera completa cortada por el plano).
        """
        radio = float(rolling_sphere_radius)
        superficies, sin_esfera, evaluables = _construir_superficies(
            masts, radio, generar_mallas, forma_superficie, subdivisiones
        )

        regiones = _regiones_de_cubierta(poligonos, building_dim)
        muestras, paso_usado = _muestrear_cubierta(regiones, paso_malla)

        puntos_cobertura: List[Dict[str, Any]] = []
        puntos_desprotegidos: List[Dict[str, Any]] = []
        area_total = 0.0
        area_protegida = 0.0
        piezas_libres: Dict[Tuple[int, str], List[Any]] = defaultdict(list)
        por_prisma: Dict[str, Dict[str, float]] = {}
        for _poly, _fn, rid in regiones:
            por_prisma.setdefault(rid, {"area": 0.0, "prot": 0.0})

        puntas_xy = [(float(m.get("posicion_x", 0.0)), float(m.get("posicion_y", 0.0)), str(m.get("id", ""))) for m in masts]

        for m in muestras:
            protegido, motivo, sid = _evaluar_muestra(m, evaluables)
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
                c = parte.representative_point() if not parte.contains(parte.centroid) else parte.centroid
                zonas.append({
                    "id_prisma": regiones[r_idx][2],
                    "motivo": motivo,
                    "mensaje": MENSAJES_MOTIVO.get(motivo, ""),
                    "area_m2": round(parte.area, 2),
                    "centroide": {"x": round(c.x, 3), "y": round(c.y, 3), "z": round(float(z_fn(c.x, c.y)), 3)},
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
        elif not evaluables:
            advertencias.append(
                "Se necesitan al menos 3 mástiles no alineados para formar una terna y calcular la esfera rodante."
            )
        if sin_esfera:
            advertencias.append(
                f"{len(sin_esfera)} terna(s) de mástiles no admiten una esfera de R = {radio:g} m. "
                "Reubique los mástiles indicados en 'triangulos_sin_esfera'."
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
        - mallas_cobertura: esferas por terna (y ternas sin esfera posible).
          Por defecto sin vértices/triángulos (se regeneran con centro y radio);
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
            item = {"tipo": "esfera", **{k: v for k, v in s.items() if k not in ("vertices", "triangulos")}}
            if incluir_malla:
                item["vertices"], item["triangulos"] = s.get("vertices", []), s.get("triangulos", [])
            mallas.append(item)
        for t in evaluacion.get("triangulos_sin_esfera", []):
            mallas.append({"tipo": "terna_sin_esfera", **t})

        return protegidas, vulnerables, mallas