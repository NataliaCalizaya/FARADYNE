import math
from typing import Any, Dict, List, Tuple, Callable, Optional

from shapely.geometry import Polygon, MultiPolygon, Point
from shapely.ops import triangulate


# ============================================================
# UTILIDADES DE NORMALIZACIÓN
# ============================================================

def normalize_point(point: Any) -> Tuple[float, float]:
    """
    Convierte un punto del Modelo2D a (x, y).

    El Modelo2D proveniente del PDFInterpreterService
    ya debe encontrarse expresado en metros.
    """
    if isinstance(point, dict):
        if "x" not in point or "y" not in point:
            raise ValueError(f"Punto sin coordenadas 'x'/'y': {point}")
        return (float(point["x"]), float(point["y"]))

    if isinstance(point, (list, tuple)):
        if len(point) < 2:
            raise ValueError(
                f"Punto con cantidad insuficiente de coordenadas: {point}"
            )
        return (float(point[0]), float(point[1]))

    raise ValueError(f"Formato de punto no reconocido: {point}")


def normalize_footprint(region: Dict[str, Any]) -> List[Tuple[float, float]]:
    """
    Obtiene y normaliza la geometría 2D de una región.

    Compatible con: region["puntos"], region["points"], region["footprint"]
    """
    footprint = (
        region.get("puntos")
        or region.get("footprint")
        or region.get("points")
        or []
    )

    if not isinstance(footprint, list):
        raise ValueError("La geometría de la región debe ser una lista de puntos.")

    return [normalize_point(point) for point in footprint]


# ============================================================
# NIVELES
# ============================================================

def get_level_value(level: Dict[str, Any]) -> Optional[float]:
    """Obtiene el valor Z del nivel (ya en metros)."""
    if not isinstance(level, dict):
        return None

    value = level.get("valor")

    if value is None:
        value = level.get("value")

    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_level_position(level: Dict[str, Any]) -> Tuple[float, float]:
    """Obtiene la posición XY del nivel (ya en metros)."""
    if not isinstance(level, dict):
        return 0.0, 0.0

    # x / y directos
    if "x" in level and "y" in level:
        try:
            return (float(level["x"]), float(level["y"]))
        except (TypeError, ValueError):
            pass

    posicion = level.get("posicion")

    # posicion = {"x": ..., "y": ...}
    if isinstance(posicion, dict):
        try:
            return (float(posicion.get("x", 0.0)), float(posicion.get("y", 0.0)))
        except (TypeError, ValueError):
            return 0.0, 0.0

    # posicion = [x, y]
    if isinstance(posicion, (list, tuple)) and len(posicion) >= 2:
        try:
            return (float(posicion[0]), float(posicion[1]))
        except (TypeError, ValueError):
            return 0.0, 0.0

    return 0.0, 0.0


# ============================================================
# NIVELES DE UNA REGIÓN
# ============================================================

def extract_region_levels(region: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Obtiene todos los niveles asociados a una región. No elimina niveles.

    Cada nivel queda como:
        {"value": 7.50, "x": 10.0, "y": 20.0, "lado": 2}
    """
    result: List[Dict[str, Any]] = []

    niveles = region.get("niveles", [])

    if not isinstance(niveles, list):
        return result

    for nivel in niveles:
        if not isinstance(nivel, dict):
            continue

        value = get_level_value(nivel)

        if value is None:
            continue

        # Cuando el nivel ya está asociado, el punto proyectado sobre el lado
        # representa la arista de la cubierta mejor que la posición visual
        # de su etiqueta.
        punto_lado = nivel.get("punto_lado")
        if isinstance(punto_lado, dict):
            try:
                x = float(punto_lado["x"])
                y = float(punto_lado["y"])
            except (KeyError, TypeError, ValueError):
                x, y = get_level_position(nivel)
        else:
            x, y = get_level_position(nivel)

        result.append(
            {
                "value": value,
                "x": x,
                "y": y,
                "lado": nivel.get("lado"),
            }
        )

    return result


def _as_level_point(nivel: Any) -> Optional[Dict[str, Any]]:
    """Convierte un nivel (nivel_bajo / nivel_alto) al formato de extract_region_levels."""
    if not isinstance(nivel, dict):
        return None
    r = extract_region_levels({"niveles": [nivel]})
    return r[0] if r else None


def _slope_direction(
    region: Dict[str, Any],
    bajo: Optional[Dict[str, Any]],
    alto: Optional[Dict[str, Any]],
) -> Optional[Tuple[float, float]]:
    """
    Vector unitario paralelo a los lados bajo/alto (las curvas de nivel).
    Si los lados no son paralelos se promedia ponderando por largo.
    """
    pts = normalize_footprint(region)

    def arista(n):
        lado = n.get("lado") if n else None
        if not isinstance(lado, int) or isinstance(lado, bool):
            return None
        if not 0 <= lado < len(pts):
            return None
        a, b = pts[lado], pts[(lado + 1) % len(pts)]
        return (b[0] - a[0], b[1] - a[1])

    da, db = arista(alto), arista(bajo)

    if da and db:
        if da[0] * db[0] + da[1] * db[1] < 0:
            db = (-db[0], -db[1])
        d = (da[0] + db[0], da[1] + db[1])  # el lado más largo pesa más
        if math.hypot(*d) < 1e-9:
            d = da
    else:
        d = da or db

    if not d:
        return None

    largo = math.hypot(*d)

    if largo < 1e-9:
        return None

    return (d[0] / largo, d[1] / largo)


def prepare_region_levels(region: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepara los niveles de una región para el modelo 3D.

    Se conservan todos los niveles. Para la pendiente se usan nivel_bajo y
    nivel_alto (ya calculados por NivelesUtils); si no existen, el primer y
    último nivel.
    """
    prepared = dict(region)

    levels = extract_region_levels(region)

    prepared["levels"] = [level["value"] for level in levels]
    prepared["level_points"] = levels

    bajo = _as_level_point(region.get("nivel_bajo"))
    alto = _as_level_point(region.get("nivel_alto"))

    prepared["slope_dir"] = None

    if bajo and alto:
        prepared["slope_pair"] = [bajo, alto]
        try:
            prepared["slope_dir"] = _slope_direction(
                region, region.get("nivel_bajo"), region.get("nivel_alto")
            )
        except (ValueError, TypeError, KeyError):
            prepared["slope_dir"] = None
    elif len(levels) >= 2:
        prepared["slope_pair"] = [levels[0], levels[-1]]
    else:
        prepared["slope_pair"] = []

    return prepared


# ============================================================
# PLANO SUPERIOR
# ============================================================

def top_plane(
    region: Dict[str, Any]
) -> Tuple[Callable[[float, float], float], float, float]:
    """
    Calcula la altura z(x, y) de la cubierta.

    Con dirección de pendiente (slope_dir) las curvas de nivel son paralelas
    a los lados: el lado alto queda a altura constante en todo su largo y
    baja linealmente hasta el lado bajo. Sin dirección se usa el plano
    z = A*x + B*y + C por dos puntos.

    Si la región heredó la caída de una vecina (slope_override, ver
    inherit_neighbor_slopes), se usa ese plano directamente.

    Todas las coordenadas XY y valores Z están en metros.
    """
    # Plano heredado de una cubierta vecina
    override = region.get("slope_override")
    if override:
        return override

    levels = region.get("levels", [])
    pair = region.get("slope_pair", [])

    # ========================================================
    # CUBIERTA INCLINADA
    # ========================================================

    if len(pair) == 2:
        a = pair[0]
        b = pair[1]

        try:
            x1 = float(a["x"]); y1 = float(a["y"]); z1 = float(a["value"])
            x2 = float(b["x"]); y2 = float(b["y"]); z2 = float(b["value"])

            zlow, zhigh = min(z1, z2), max(z1, z2)
            direction = region.get("slope_dir")

            # Solo importa la distancia perpendicular al lado.
            if direction:
                ux, uy = direction
                nx, ny = -uy, ux
                h = (x2 - x1) * nx + (y2 - y1) * ny

                if abs(h) > 1e-6:
                    k = (z2 - z1) / h

                    def z_function(x: float, y: float) -> float:
                        z = z1 + k * ((x - x1) * nx + (y - y1) * ny)
                        z = min(max(z, zlow), zhigh)
                        return max(0.0, float(z))

                    return z_function, zlow, zhigh

            # Fallback: lógica anterior (A*x + B*y + C)
            dx = x2 - x1
            dy = y2 - y1
            den = dx * dx + dy * dy

            if den > 1e-9:
                dz = z2 - z1
                A = dz * dx / den
                B = dz * dy / den
                C = z1 - A * x1 - B * y1

                def z_function(x: float, y: float) -> float:
                    return max(0.0, float(A * x + B * y + C))

                return z_function, zlow, zhigh

        except (KeyError, TypeError, ValueError):
            pass

    # ========================================================
    # UN SOLO NIVEL
    # ========================================================

    valid_levels = []

    if isinstance(levels, list):
        for level in levels:
            try:
                valid_levels.append(float(level))
            except (TypeError, ValueError):
                continue

    if valid_levels:
        z = max(valid_levels)
        return (lambda x, y: max(0.0, z), z, z)

    # ========================================================
    # FALLBACK
    # ========================================================

    z = 3.7
    return (lambda x, y: z, z, z)


# ============================================================
# HERENCIA DE CAÍDA ENTRE CUBIERTAS VECINAS
# ============================================================

def _shared_edge(
    mine: Polygon, other: Polygon, tol: float = 0.05
) -> Optional[Tuple[Tuple[float, float], Tuple[float, float], float]]:
    """
    Tramo de borde que `other` comparte con `mine`.
    Devuelve (punto_a, punto_b, largo) o None.

    Junta TODOS los tramos alineados con el más largo (el borde compartido
    puede venir partido en varias piezas) y devuelve sus extremos reales.
    """
    try:
        inter = other.boundary.intersection(mine.buffer(tol))
    except Exception:
        return None

    if inter.is_empty:
        return None

    partes = list(inter.geoms) if hasattr(inter, "geoms") else [inter]
    lineas = [g for g in partes if g.geom_type == "LineString" and g.length > 1e-9]

    if not lineas:
        return None

    base = max(lineas, key=lambda g: g.length)
    c = list(base.coords)
    ox, oy = float(c[0][0]), float(c[0][1])
    dx, dy = float(c[-1][0]) - ox, float(c[-1][1]) - oy
    norm = math.hypot(dx, dy)

    if norm < 1e-9:
        return None

    ux, uy = dx / norm, dy / norm
    ts: List[float] = []

    for g in lineas:
        gc = list(g.coords)
        gdx, gdy = gc[-1][0] - gc[0][0], gc[-1][1] - gc[0][1]
        gn = math.hypot(gdx, gdy)

        if gn < 1e-9 or abs((gdx * ux + gdy * uy) / gn) < 0.98:
            continue

        for px, py in gc:
            ts.append((px - ox) * ux + (py - oy) * uy)

    if not ts:
        return None

    tmin, tmax = min(ts), max(ts)
    largo = tmax - tmin

    if largo <= 1e-9:
        return None

    return (
        (ox + ux * tmin, oy + uy * tmin),
        (ox + ux * tmax, oy + uy * tmax),
        float(largo),
    )


def _tiene_pendiente(r: Dict[str, Any]) -> bool:
    """
    True si la cubierta ya tiene una caída real (propia o heredada).

    Un par de niveles con la MISMA altura (ej. dos veces +7.90, típico de
    una pared doble o de un nivel compartido) es una cubierta plana, no una
    pendiente: puede heredar la caída de su vecina.
    """
    if r.get("slope_override"):
        return True

    pair = r.get("slope_pair", [])

    if len(pair) != 2:
        return False

    try:
        return abs(float(pair[0]["value"]) - float(pair[1]["value"])) > 1e-6
    except (KeyError, TypeError, ValueError):
        return False


def inherit_neighbor_slopes(
    regions_3d: List[Dict[str, Any]],
    min_shared: float = 0.5,
    min_drop: float = 0.05,
    tol: float = 0.25,
    max_passes: int = 10,
) -> List[Tuple[Any, Any]]:
    """
    Una cubierta sin pendiente propia (menos de 2 niveles) que comparte un
    lado con una cubierta inclinada acompaña la caída de esa vecina:
    en un extremo del lado compartido toma la altura máxima y en el otro la
    mínima, y entre ambos baja linealmente.

    Mejoras de robustez:
    - Prueba TODAS las vecinas candidatas (por largo de borde compartido) y
      usa la primera válida, en vez de rendirse con la más larga.
    - Preferencia por vecinas con pendiente propia; si no hay, acepta
      vecinas que ya heredaron (cadenas de piezas), hasta `max_passes` (cadenas de paredes).
    - Cada cubierta se procesa aislada: un error en una no afecta a las demás.
    - No modifica el Modelo2D.

    Devuelve la lista de (id_cubierta, id_vecina_origen) ajustadas.
    """
    polys: Dict[Any, Polygon] = {}

    for r in regions_3d:
        try:
            p = Polygon(normalize_footprint(r)).buffer(0)

            if isinstance(p, MultiPolygon):
                p = max(list(p.geoms), key=lambda g: g.area)

            if not p.is_empty and p.geom_type == "Polygon":
                polys[r.get("id")] = p
        except Exception:
            continue

    ajustadas: List[Tuple[Any, Any]] = []
    motivos: Dict[Any, str] = {}

    for _ in range(max_passes):
        fuentes = [r for r in regions_3d if _tiene_pendiente(r)]
        cambios = 0

        for r in regions_3d:
            if _tiene_pendiente(r):
                continue

            try:
                mine = polys.get(r.get("id"))
                if mine is None:
                    continue

                candidatos = []

                for idx, n in enumerate(fuentes):
                    if n is r:
                        continue

                    otro = polys.get(n.get("id"))
                    if otro is None:
                        continue

                    edge = _shared_edge(mine, otro, tol)

                    if edge and edge[2] >= min_shared:
                        heredada = 1 if n.get("slope_override") else 0
                        candidatos.append((heredada, -edge[2], idx, n, edge))

                candidatos.sort(key=lambda c: (c[0], c[1], c[2]))

                propios = [
                    v
                    for v in (r.get("levels") or [])
                    if isinstance(v, (int, float))
                ]

                heredo = False

                for _her, _neg, _idx, vecina, (a, b, _largo) in candidatos:
                    vid = vecina.get("id")
                    zfun_v, zlow_v, zhigh_v = top_plane(vecina)

                    za = float(zfun_v(*a))
                    zb = float(zfun_v(*b))

                    if not (math.isfinite(za) and math.isfinite(zb)):
                        motivos[r.get("id")] = f"{vid}: altura no válida"
                        continue

                    # El borde compartido tiene que bajar de verdad
                    if abs(za - zb) < min_drop:
                        motivos[r.get("id")] = (
                            f"{vid}: borde compartido horizontal "
                            f"({za:.2f} / {zb:.2f} m)"
                        )
                        continue

                    # Un nivel propio fuera del rango de la vecina indica que
                    # es otra cubierta distinta: no se toca.
                    if any(
                        v < zlow_v - 0.05 or v > zhigh_v + 0.05 for v in propios
                    ):
                        motivos[r.get("id")] = (
                            f"{vid}: su nivel {propios} queda fuera de "
                            f"{zlow_v:.2f}-{zhigh_v:.2f} m"
                        )
                        continue

                    dx, dy = b[0] - a[0], b[1] - a[1]
                    den = dx * dx + dy * dy

                    if den < 1e-9:
                        continue

                    def z_function(
                        x, y, a=a, za=za, zb=zb, dx=dx, dy=dy, den=den
                    ):
                        t = ((x - a[0]) * dx + (y - a[1]) * dy) / den
                        t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
                        return max(0.0, float(za + t * (zb - za)))

                    r["slope_override"] = (z_function, min(za, zb), max(za, zb))
                    r["slope_source"] = vecina.get("id")
                    ajustadas.append((r.get("id"), vecina.get("id")))
                    motivos.pop(r.get("id"), None)
                    cambios += 1
                    heredo = True
                    break

            except Exception as exc:
                print(
                    f"[MODELO 3D] No se pudo heredar pendiente "
                    f"id={r.get('id')}: {exc}"
                )
                continue

        if not cambios:
            break

    # Cubiertas que tocan una vecina inclinada pero no se pudieron ajustar.
    for rid, motivo in motivos.items():
        print(f"[MODELO 3D] Sin heredar caída id={rid} -> {motivo}")

    return ajustadas


# ============================================================
# GENERACIÓN DE PRISMA 3D
# ============================================================

MAX_RING_VERTICES = 2000


def _densificar_anillo(pts, zfun, tol=0.01, max_depth=10):
    """
    Inserta vértices en las aristas donde z(x, y) no es lineal
    (por ejemplo donde se recorta en zlow / zhigh), para que
    las paredes sigan exactamente la caída de la tapa.
    """
    def partir(a, b, za, zb, depth):
        m = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        zm = float(zfun(m[0], m[1]))
        if depth >= max_depth or abs(zm - (za + zb) / 2.0) <= tol:
            return []
        return (
            partir(a, m, za, zm, depth + 1)
            + [m]
            + partir(m, b, zm, zb, depth + 1)
        )

    salida = []
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        salida.append(a)
        salida.extend(
            partir(a, b, float(zfun(*a)), float(zfun(*b)), 0)
        )
    return salida


def _ear_clip(pts: List[Tuple[float, float]]):
    """Triangulación por recorte de orejas (respaldo, polígonos sin huecos)."""
    n = len(pts)
    if n < 3:
        return []

    area2 = sum(
        pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1]
        for i in range(n)
    )
    idx = list(range(n))
    if area2 < 0:
        idx.reverse()

    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def inside(p, a, b, c):
        return (
            cross(a, b, p) > 1e-9
            and cross(b, c, p) > 1e-9
            and cross(c, a, p) > 1e-9
        )

    tris = []
    guard = 0

    while len(idx) > 3 and guard < 20000:
        guard += 1
        m = len(idx)
        found = False

        for k in range(m):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % m]
            a, b, c = pts[i0], pts[i1], pts[i2]

            if cross(a, b, c) <= 1e-12:
                continue

            if any(
                inside(pts[j], a, b, c) for j in idx if j not in (i0, i1, i2)
            ):
                continue

            tris.append([a, b, c])
            idx.pop(k)
            found = True
            break

        if not found:
            # Destraba quitando el vértice más colineal.
            m = len(idx)
            k = min(
                range(m),
                key=lambda q: abs(
                    cross(pts[idx[q - 1]], pts[idx[q]], pts[idx[(q + 1) % m]])
                ),
            )
            idx.pop(k)

    if len(idx) == 3:
        a, b, c = pts[idx[0]], pts[idx[1]], pts[idx[2]]
        if abs(cross(a, b, c)) > 1e-12:
            tris.append([a, b, c])

    return tris


def _triangulate_top(poly_d: Polygon) -> List[List[Tuple[float, float]]]:
    """
    Triangula la huella (ya con los vértices densificados) respetando sus
    bordes. Usa Delaunay con restricciones si Shapely lo ofrece (>= 2.1);
    si no, Delaunay común filtrado. Si la suma de áreas no coincide con la
    del polígono (huecos en la tapa), prueba el recorte de orejas.
    """
    tris: List[List[Tuple[float, float]]] = []

    try:
        import shapely

        cdt = getattr(shapely, "constrained_delaunay_triangles", None)

        if cdt is not None:
            for t in cdt(poly_d).geoms:
                tris.append([(float(x), float(y)) for x, y in list(t.exterior.coords)[:-1]])
    except Exception:
        tris = []

    if not tris:
        poly_tol = poly_d.buffer(1e-6)

        for t in triangulate(poly_d):
            if not poly_tol.covers(t):
                continue

            c = list(t.exterior.coords)[:-1]
            if len(c) == 3:
                tris.append([(float(x), float(y)) for x, y in c])

    def error(ts):
        total = sum(Polygon(t).area for t in ts)
        return abs(total - poly_d.area) / max(poly_d.area, 1e-9)

    if (not tris or error(tris) > 0.005) and not list(poly_d.interiors):
        pts = [(float(x), float(y)) for x, y in list(poly_d.exterior.coords)[:-1]]
        alt = _ear_clip(pts)

        if alt and (not tris or error(alt) < error(tris)):
            tris = alt

    return tris


def add_prism_with_roof(region: Dict[str, Any]) -> Dict[str, Any]:
    vacio = {"id": region.get("id"), "faces": [], "vertices": []}

    try:
        fp = normalize_footprint(region)
    except (ValueError, TypeError, KeyError) as exc:
        return {**vacio, "error": str(exc)}

    if len(fp) < 3:
        return vacio

    # POLÍGONO
    try:
        poly = Polygon(fp).buffer(0)
    except Exception as exc:
        return {**vacio, "error": f"No se pudo construir la geometría: {exc}"}

    if poly.is_empty:
        return vacio

    if isinstance(poly, MultiPolygon):
        polygons = list(poly.geoms)

        if not polygons:
            return vacio

        poly = max(polygons, key=lambda p: p.area)

    if poly.geom_type != "Polygon":
        return vacio

    # PLANO DE TECHO
    zfun, zlow, zhigh = top_plane(region)

    base = 0.0

    # VÉRTICES 2D
    pts0 = [(float(x), float(y)) for x, y in list(poly.exterior.coords)[:-1]]

    if len(pts0) < 3:
        return vacio

    # Vértices extra donde la altura no es lineal: las paredes y la tapa
    # comparten exactamente los mismos vértices, así no quedan grietas.
    pts = _densificar_anillo(pts0, zfun)
    poly_d = poly

    if len(pts) > MAX_RING_VERTICES:
        pts = pts0
    else:
        try:
            candidato = Polygon(pts, [list(i.coords) for i in poly.interiors])

            if (
                candidato.is_valid
                and abs(candidato.area - poly.area) <= 1e-6 * max(poly.area, 1.0)
            ):
                poly_d = candidato
            else:
                pts = pts0
        except Exception:
            pts = pts0

    top = [(x, y, float(zfun(x, y))) for x, y in pts]
    bot = [(x, y, base) for x, y in pts]

    faces: List[Dict[str, Any]] = []

    # PAREDES LATERALES
    for i in range(len(pts)):
        j = (i + 1) % len(pts)

        # Arista de largo cero o pared sin altura: no aporta cara.
        if math.hypot(pts[j][0] - pts[i][0], pts[j][1] - pts[i][1]) < 1e-9:
            continue

        if top[i][2] <= base + 1e-6 and top[j][2] <= base + 1e-6:
            continue

        faces.append(
            {"type": "side", "points": [bot[i], bot[j], top[j], top[i]]}
        )

    # TAPAS SUPERIOR E INFERIOR
    for tri in _triangulate_top(poly_d):
        top_triangle = [(x, y, float(zfun(x, y))) for x, y in tri]
        bottom_triangle = [(x, y, base) for x, y in tri]

        faces.append({"type": "top", "points": top_triangle})
        faces.append({"type": "bottom", "points": list(reversed(bottom_triangle))})

    return {
        "id": region.get("id"),
        "faces": faces,
        "top_vertices": top,
        "bottom_vertices": bot,
        "zlow": zlow,
        "zhigh": zhigh,
        "niveles": region.get("niveles", []),
        "tipo": region.get("tipo", "poligono"),
        "tipo_cubierta": region.get("tipo_cubierta", "pendiente_por_resolver"),
        "capa": region.get("capa"),
        "heredada_de": region.get("slope_source"),
    }


# ============================================================
# BOUNDING BOX
# ============================================================

def calculate_bbox(
    regions: List[Dict[str, Any]]
) -> Tuple[float, float, float, float]:
    points: List[Tuple[float, float]] = []

    for region in regions:
        try:
            points.extend(normalize_footprint(region))
        except (ValueError, TypeError, KeyError):
            continue

    if not points:
        return (0.0, 0.0, 80.0, 20.0)

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]

    return (min(xs), min(ys), max(xs), max(ys))


# ============================================================
# REGIONES VÁLIDAS
# ============================================================

def prepare_3d_regions(regions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    valid_regions: List[Dict[str, Any]] = []

    if not isinstance(regions, list):
        return valid_regions

    for region in regions:
        if not isinstance(region, dict):
            continue

        try:
            footprint = normalize_footprint(region)

            if len(footprint) < 3:
                continue

            polygon = Polygon(footprint).buffer(0)

            if polygon.is_empty:
                continue

            if isinstance(polygon, MultiPolygon):
                polygons = list(polygon.geoms)

                if not polygons:
                    continue

                polygon = max(polygons, key=lambda p: p.area)

            if polygon.geom_type != "Polygon":
                continue

            prepared = dict(region)

            # El Modelo2D ya viene en metros.
            prepared["footprint"] = [(float(x), float(y)) for x, y in footprint]

            prepared = prepare_region_levels(prepared)

            valid_regions.append(prepared)

        except (ValueError, TypeError, KeyError) as exc:
            print(f"[MODELO 3D] Región ignorada id={region.get('id')}: {exc}")

        except Exception as exc:
            print(
                f"[MODELO 3D] Error procesando región id={region.get('id')}: {exc}"
            )

    return valid_regions


# ============================================================
# SERVICIO PRINCIPAL
# ============================================================

class Model3DGeneratorService:
    """
    Genera el Modelo 3D a partir del Modelo2D.

    IMPORTANTE: el PDFInterpreterService debe entregar units = "meters" y
    todas las coordenadas XY deben estar expresadas en metros.

    Este servicio NO vuelve a aplicar ningún factor de escala.
    """

    @staticmethod
    def generate_3d_mesh_from_2d(
        modelo2d_data: Dict[str, Any],
        tank_threshold: float = 9.30,
    ) -> Dict[str, Any]:

        # VALIDACIÓN
        if not isinstance(modelo2d_data, dict):
            raise ValueError("Los datos del Modelo2D deben ser un diccionario.")

        # UNIDADES
        units = str(modelo2d_data.get("units", "m")).lower()

        if units not in ("m", "meter", "meters", "metro", "metros"):
            raise ValueError(
                "El Modelo3D espera un Modelo2D "
                "con coordenadas expresadas en metros. "
                f"Unidades recibidas: {units}"
            )

        # REGIONES
        regions = (
            modelo2d_data.get("poligonos")
            or modelo2d_data.get("roof_regions")
            or []
        )

        # COTAS
        cotas = (
            modelo2d_data.get("cotas_altura")
            or modelo2d_data.get("cotas_alturas")
            or []
        )

        # LEVEL MARKS
        level_marks = modelo2d_data.get("level_marks") or []

        all_level_marks = level_marks or cotas

        # REGIONES 3D
        regions_3d = prepare_3d_regions(regions)

        # Las cubiertas sin pendiente propia acompañan la caída de su vecina
        try:
            ajustadas = inherit_neighbor_slopes(regions_3d)
        except Exception as exc:
            ajustadas = []
            print(f"[MODELO 3D] Herencia de pendientes omitida: {exc}")

        if ajustadas:
            detalle = ", ".join(f"{a}<-{b}" for a, b in ajustadas)
            print(
                "[MODELO 3D] Cubiertas que heredaron la caída de su vecina "
                f"({len(ajustadas)}): {detalle}"
            )

        # FALLBACK
        if not regions_3d:
            print("[MODELO 3D] No se encontraron regiones válidas.")

            return {
                "units": "m",
                "bbox": [0.0, 0.0, 80.0, 20.0],
                "regions": [],
                "prisms": [],
                "tank": None,
                "region_count": 0,
                "levels": [],
                "level_marks": all_level_marks,
                "vista_defecto": {
                    "camera": [76.0, 15.0, 76.0],
                    "target": [40.0, 3.0, 10.0],
                },
            }

        # BOUNDING BOX
        bbox = calculate_bbox(regions_3d)
        bx0, by0, bx1, by1 = bbox

        center_x = (bx0 + bx1) / 2.0
        center_y = (by0 + by1) / 2.0
        size = max(bx1 - bx0, by1 - by0, 20.0)

        # PRISMAS
        prisms: List[Dict[str, Any]] = []

        for region in regions_3d:
            try:
                prism_data = add_prism_with_roof(region)

                if prism_data.get("faces"):
                    prisms.append(prism_data)

            except Exception as exc:
                print(
                    f"[MODELO 3D] Error generando prisma id={region.get('id')}: {exc}"
                )

        # NIVELES GENERALES
        levels: List[float] = []

        for mark in all_level_marks:
            if not isinstance(mark, dict):
                continue

            value = get_level_value(mark)

            if value is not None:
                levels.append(value)

        levels = sorted(set(levels))

        # METADATA
        # Nota: "regions" se serializa; el plano heredado (una función) no
        # es serializable, así que se quita de la copia que se devuelve.
        regions_out = [
            {k: v for k, v in r.items() if k != "slope_override"}
            for r in regions_3d
        ]

        metadata = {
            "units": "m",
            "bbox": list(bbox),
            "regions": regions_out,
            "prisms": prisms,
            "region_count": len(regions_3d),
            "levels": levels,
            "level_marks": all_level_marks,
            "vista_defecto": {
                "camera": [
                    round(center_x + size * 0.95, 2),
                    round(size * 0.75, 2),
                    round(center_y + size * 0.95, 2),
                ],
                "target": [
                    round(center_x, 2),
                    3.0,
                    round(center_y, 2),
                ],
            },
        }

        print(
            "[MODELO 3D] Generación finalizada. "
            f"Regiones={len(regions_3d)}, "
            f"Prismas={len(prisms)}, "
            f"Niveles={len(levels)}, "
            "Unidades=m"
        )

        return metadata


def get_altura_en_punto(
    poligonos: List[Dict[str, Any]],
    x: float,
    y: float,
    default: float = 0.0,
) -> float:
    """
    Dado un punto (x, y) del Modelo2D, busca en qué polígono cae y devuelve
    la altura (Z) de la cubierta en ese punto exacto, usando el mismo
    cálculo de plano (top_plane) que usa el generador de Modelo 3D.

    Si el punto no cae dentro de ningún polígono, devuelve `default`
    (0.0 = nivel de piso; es un caso válido, ej. mástil perimetral en el
    suelo, no un error).
    """
    punto = Point(x, y)

    for region in poligonos:
        try:
            footprint = normalize_footprint(region)
            if len(footprint) < 3:
                continue

            poly = Polygon(footprint)
            if not poly.is_valid or not (poly.contains(punto) or poly.touches(punto)):
                continue

            prepared = prepare_region_levels(region)
            z_function, _, _ = top_plane(prepared)
            return round(float(z_function(x, y)), 3)

        except (ValueError, TypeError):
            continue

    return default