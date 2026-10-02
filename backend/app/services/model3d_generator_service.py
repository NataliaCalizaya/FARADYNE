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

    Todas las coordenadas XY y valores Z están en metros.
    """
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
# GENERACIÓN DE PRISMA 3D
# ============================================================

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
    pts = [(float(x), float(y)) for x, y in list(poly.exterior.coords)[:-1]]

    if len(pts) < 3:
        return vacio

    top = [(x, y, float(zfun(x, y))) for x, y in pts]
    bot = [(x, y, base) for x, y in pts]

    faces: List[Dict[str, Any]] = []

    # PAREDES LATERALES
    for i in range(len(pts)):
        j = (i + 1) % len(pts)

        faces.append(
            {"type": "side", "points": [bot[i], bot[j], top[j], top[i]]}
        )

    # TAPAS SUPERIOR E INFERIOR
    # Shapely triangula y se conservan únicamente los triángulos
    # completamente cubiertos por la huella 2D original (polígonos cóncavos).
    for triangle in triangulate(poly):
        if not poly.covers(triangle):
            continue

        triangle_points = list(triangle.exterior.coords)[:-1]
        if len(triangle_points) != 3:
            continue

        top_triangle = [
            (float(x), float(y), float(zfun(x, y))) for x, y in triangle_points
        ]
        bottom_triangle = [(float(x), float(y), base) for x, y in triangle_points]

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
        metadata = {
            "units": "m",
            "bbox": list(bbox),
            "regions": regions_3d,
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