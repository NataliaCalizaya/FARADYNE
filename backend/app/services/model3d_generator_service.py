from typing import Any, Dict, List, Tuple, Callable
import math
from shapely.geometry import Polygon


def top_plane(region: Dict[str, Any]) -> Tuple[Callable[[float, float], float], float, float]:
    """Calculates top plane height interpolation function z = Ax + By + C for a given region."""
    levels = region.get('levels', [])
    pair = region.get('slope_pair', [])
    if len(pair) == 2:
        a, b = pair[0], pair[1]
        dx, dy = b['x'] - a['x'], b['y'] - a['y']
        den = dx * dx + dy * dy
        if den > 1e-9:
            dz = b['value'] - a['value']
            A = dz * dx / den
            B = dz * dy / den
            C = a['value'] - A * a['x'] - B * a['y']
            return lambda x, y: max(0.0, A * x + B * y + C), min(a['value'], b['value']), max(a['value'], b['value'])
    z = max(levels) if levels else 3.7
    return lambda x, y: z, z, z


def add_prism_with_roof(region: Dict[str, Any]) -> Dict[str, Any]:
    """Generates 3D faces (top sloped roof, side walls, bottom base) for a region using top_plane."""
    fp = region.get('footprint') or region.get('points', [])
    if len(fp) < 3:
        return {"faces": [], "vertices": []}

    zfun, zlow, zhigh = top_plane(region)
    base = 0.0

    poly = Polygon(fp).buffer(0)
    if poly.is_empty or poly.geom_type != 'Polygon':
        return {"faces": [], "vertices": []}

    pts = [(float(x), float(y)) for x, y in list(poly.exterior.coords)[:-1]]
    top = [(x, y, float(zfun(x, y))) for x, y in pts]
    bot = [(x, y, base) for x, y in pts]

    faces = []
    # Side walls
    for i in range(len(pts)):
        j = (i + 1) % len(pts)
        faces.append({"type": "side", "points": [bot[i], bot[j], top[j], top[i]]})

    # Top surface (fan triangulation)
    for i in range(1, len(top) - 1):
        faces.append({"type": "top", "points": [top[0], top[i], top[i + 1]]})

    # Base surface
    for i in range(1, len(bot) - 1):
        faces.append({"type": "bottom", "points": [bot[0], bot[i + 1], bot[i]]})

    return {
        "id": region.get("id"),
        "faces": faces,
        "top_vertices": top,
        "bottom_vertices": bot,
        "zlow": zlow,
        "zhigh": zhigh,
    }


def calculate_bbox(regions: List[Dict[str, Any]]) -> Tuple[float, float, float, float]:
    pts = [p for r in regions for p in (r.get('footprint') or r.get('points', []))]
    if not pts:
        return (0.0, 0.0, 80.0, 20.0)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


class Model3DGeneratorService:
    """Service to programmatically generate 3D volumetric geometry from 2D model data using sloped top_plane interpolation."""

    @staticmethod
    def generate_3d_mesh_from_2d(modelo2d_data: Dict[str, Any], tank_threshold: float = 9.30) -> Dict[str, Any]:
        """Reads 2D model regions & levels, extrudes 3D volumes with sloped roofs and detects tank structure."""
        regions = modelo2d_data.get("poligonos") or modelo2d_data.get("roof_regions", [])
        cotas = modelo2d_data.get("cotas_altura", [])
        level_marks = modelo2d_data.get("level_marks", [])

        if not regions:
            # Fallback default region
            regions = [{
                "id": "R01",
                "footprint": [(0, 0), (20, 0), (20, 15), (0, 15)],
                "levels": [4.0, 7.5],
                "level_marks": [],
                "slope_pair": [
                    {"value": 4.0, "x": 0, "y": 0},
                    {"value": 7.5, "x": 20, "y": 15}
                ]
            }]

        bbox = calculate_bbox(regions)
        bx0, by0, bx1, by1 = bbox
        center_x = (bx0 + bx1) / 2.0
        center_y = (by0 + by1) / 2.0
        size = max(bx1 - bx0, by1 - by0, 20.0)

        prisms = []
        for region in regions:
            prism_data = add_prism_with_roof(region)
            if prism_data.get("faces"):
                prisms.append(prism_data)

        # Detect Tank (elemento elevado) around configurable tank_threshold (default +9.30)
        tank = None
        high_marks = [m for m in (level_marks or cotas) if abs(m.get("valor", m.get("value", 0)) - tank_threshold) < 0.05]
        if high_marks:
            p = high_marks[0]
            tx = p.get("x", p.get("posicion", [0, 0])[0])
            ty = p.get("y", p.get("posicion", [0, 0])[1])
            tw = max(2.0, (bx1 - bx0) * 0.06)
            td = max(1.5, (by1 - by0) * 0.06)
            z0 = 7.9
            z1 = tank_threshold
            tank = {
                'x': tx,
                'y': ty,
                'width': tw,
                'depth': td,
                'base': z0,
                'top': z1
            }

        metadata = {
            'bbox': list(bbox),
            'regions': regions,
            'prisms': prisms,
            'tank': tank,
            'region_count': len(regions),
            'levels': sorted(set(m.get("valor", m.get("value", 0)) for m in (level_marks or cotas) if "valor" in m or "value" in m)),
            'level_marks': level_marks or cotas,
            'vista_defecto': {
                'camera': [round(center_x + size * 0.95, 2), round(size * 0.75, 2), round(center_y + size * 0.95, 2)],
                'target': [round(center_x, 2), 3.0, round(center_y, 2)]
            }
        }

        return metadata
