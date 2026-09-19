import fitz  # PyMuPDF
import io
import re
import math
import logging
from typing import Any, Dict, List, Tuple
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union, polygonize
from shapely.affinity import affine_transform

logger = logging.getLogger("faradyne.pdf")

# Regex patterns matching reference implementation
LEVEL_RE = re.compile(r'\+\s*(\d+(?:[.,]\d+)?)')
SLOPE_RE = re.compile(r'PEND\.?\s*(\d+(?:[.,]\d+)?)\s*%', re.IGNORECASE)


def parse_levels(text: str) -> List[float]:
    out = []
    for m in LEVEL_RE.finditer(text or ''):
        try:
            v = float(m.group(1).replace(',', '.'))
            if 0 <= v <= 100:
                out.append(v)
        except ValueError:
            pass
    return sorted(set(out))


def rotate_point(x: float, y: float, page_w: float, page_h: float, rotation: int) -> Tuple[float, float]:
    r = rotation % 360
    if r == 90:
        return page_h - y, x
    if r == 180:
        return page_w - x, page_h - y
    if r == 270:
        return y, page_w - x
    return x, y


def drawing_lines(page, wanted_color=None) -> List[LineString]:
    result = []
    for di, d in enumerate(page.get_drawings()):
        color = d.get('color')
        if wanted_color is not None:
            if color is None or any(abs(color[i] - wanted_color[i]) > 0.02 for i in range(3)):
                continue
        for si, item in enumerate(d.get('items', [])):
            if item[0] == 'l':
                a, b = item[1], item[2]
                if math.hypot(b.x - a.x, b.y - a.y) > 1.5:
                    result.append(LineString([(a.x, a.y), (b.x, b.y)]))
            elif item[0] == 're':
                r = item[1]
                pts = [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)]
                for j in range(4):
                    a, b = pts[j], pts[(j + 1) % 4]
                    if math.hypot(b[0] - a[0], b[1] - a[1]) > 1.5:
                        result.append(LineString([a, b]))
    return result


def to_model_geom(poly, page_size: List[float], rotation: int):
    page_w, page_h = page_size
    r = rotation % 360
    if r == 270:
        return affine_transform(poly, [0, 1, -1, 0, 0, page_w])
    if r == 90:
        return affine_transform(poly, [0, -1, 1, 0, page_h, 0])
    if r == 180:
        return affine_transform(poly, [-1, 0, 0, -1, page_w, page_h])
    return poly


def detect_roof_regions(data: bytes, model_meta: dict) -> List[dict]:
    doc = fitz.open(stream=data, filetype='pdf')
    page = doc[0]
    page_size = model_meta.get('page_size', [600, 800])
    rotation = model_meta.get('rotation', 0)

    all_lines = drawing_lines(page)
    red_lines = drawing_lines(page, (1.0, 0.0, 0.0))
    if not all_lines:
        return []

    all_polys = list(polygonize(unary_union(all_lines)))
    red_polys = list(polygonize(unary_union(red_lines))) if red_lines else []
    bbox = unary_union(all_lines).bounds
    drawing_area = max(1.0, (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))

    candidates = []
    for p in red_polys:
        if p.area >= drawing_area * 0.010 and p.area <= drawing_area * 0.40:
            candidates.append(p)

    roof_pts = [Point(x['x'], x['y']) for x in model_meta.get('roof_labels', [])]
    for p in sorted(all_polys, key=lambda q: q.area, reverse=True):
        if p.area < drawing_area * 0.03 or p.area > drawing_area * 0.60:
            continue
        if any(p.contains(pt) for pt in roof_pts):
            candidates.append(p)
            break

    if candidates:
        cb = unary_union(candidates).bounds
        model_scale = 80.0 / max(cb[2] - cb[0], cb[3] - cb[1], 1.0)
    else:
        model_scale = 1.0

    unique = []
    for p in sorted(candidates, key=lambda q: q.area, reverse=True):
        if not p.is_valid:
            p = p.buffer(0)
        if p.is_empty or p.area < drawing_area * .003:
            continue
        duplicate = False
        for q in unique:
            inter = p.intersection(q).area
            union = p.union(q).area
            if union and inter / union > 0.85:
                duplicate = True
                break
        if not duplicate:
            unique.append(p)

    regions = []
    for idx, raw in enumerate(unique, 1):
        geom = to_model_geom(raw, page_size, rotation)
        geom = geom.simplify(1.5, preserve_topology=True)
        if geom.geom_type != 'Polygon' or geom.area < 1000:
            continue

        labels = sorted(model_meta.get('roof_labels', []), key=lambda l: geom.distance(Point(l['x'], l['y'])))
        region_labels = [l for l in labels if geom.distance(Point(l['x'], l['y'])) < 120][:3]

        marks = [m for m in model_meta.get('level_marks', []) if geom.contains(Point(m['x'], m['y'])) or geom.distance(Point(m['x'], m['y'])) < 30]
        if region_labels:
            anchor = min(region_labels, key=lambda l: geom.distance(Point(l['x'], l['y'])))
            local = sorted(model_meta.get('level_marks', []), key=lambda m: math.hypot(m['x'] - anchor['x'], m['y'] - anchor['y']))[:6]
            marks = [m for m in local if m in marks or math.hypot(m['x'] - anchor['x'], m['y'] - anchor['y']) < 230]
        marks = sorted(marks, key=lambda m: math.hypot(m['x'] - geom.centroid.x, m['y'] - geom.centroid.y))[:6]
        if not marks:
            marks = sorted(model_meta.get('level_marks', []), key=lambda m: geom.distance(Point(m['x'], m['y'])))[:3]

        seen = set()
        lm = []
        for m in sorted(marks, key=lambda x: x['value']):
            key = (round(m['value'], 2), round(m['x'], 1), round(m['y'], 1))
            if key not in seen:
                seen.add(key)
                lm.append(m)

        slope_target = next((l['slope_percent'] for l in region_labels if l.get('slope_percent')), None)
        chosen = []
        if len(lm) >= 2:
            pairs = []
            for i in range(len(lm)):
                for j in range(i + 1, len(lm)):
                    a, b = lm[i], lm[j]
                    run = math.hypot(a['x'] - b['x'], a['y'] - b['y'])
                    if run < 20 or abs(a['value'] - b['value']) < .05:
                        continue
                    slope = abs(a['value'] - b['value']) / (run * model_scale) * 100
                    score = abs(slope - slope_target) if slope_target else -abs(a['value'] - b['value'])
                    pairs.append((score, a, b, slope))
            if pairs:
                best = min(pairs, key=lambda x: x[0])
                chosen = [best[1], best[2]]
        if not chosen and lm:
            chosen = [min(lm, key=lambda x: x['value']), max(lm, key=lambda x: x['value'])]

        coords = [[float(x), float(y)] for x, y in list(geom.exterior.coords)[:-1]]
        if len(coords) < 3:
            continue
        regions.append({
            'id': f'R{idx:02d}',
            'footprint': coords,
            'points': coords,  # Alias for frontend backward compatibility
            'levels': sorted(set(round(x['value'], 2) for x in lm)),
            'level_marks': [{'value': x['value'], 'x': x['x'], 'y': x['y']} for x in lm],
            'slope_percent': slope_target,
            'slope_pair': [
                {'value': chosen[0]['value'], 'x': chosen[0]['x'], 'y': chosen[0]['y']},
                {'value': chosen[1]['value'], 'x': chosen[1]['x'], 'y': chosen[1]['y']},
            ] if len(chosen) == 2 else [],
        })

    regions.sort(key=lambda r: (min(p[1] for p in r['footprint']), min(p[0] for p in r['footprint'])))
    return regions


class PDFInterpreterService:
    """Service to parse, validate and interpret 2D vector PDF drawings using PyMuPDF (fitz) and Shapely."""

    @staticmethod
    def validate_and_read_pdf(file_bytes: bytes, filename: str) -> fitz.Document:
        """Opens the PDF using PyMuPDF (fitz) and validates that it contains vector drawing paths."""
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception as err:
            logger.error(f"Failed to open PDF file {filename}: {err}")
            raise ValueError(f"El archivo PDF '{filename}' está corrupto o no se pudo abrir. Detalle: {str(err)}")

        if doc.page_count == 0:
            raise ValueError(f"El archivo PDF '{filename}' no contiene páginas.")

        has_vector_drawings = False
        for page in doc:
            drawings = page.get_drawings()
            if drawings and len(drawings) > 0:
                has_vector_drawings = True
                break

        if not has_vector_drawings:
            logger.warning(f"PDF {filename} does not contain vector drawing paths.")
            raise ValueError("El PDF no contiene geometría vectorial interpretable.")

        return doc

    @staticmethod
    def interpret_pdf_data(doc: fitz.Document, file_bytes: bytes = None) -> Dict[str, Any]:
        """Extracts layers, raw lines, level marks, roof regions via Shapely polygonization, and cotas_altura."""
        page = doc[0]
        page_w = float(page.mediabox.width)
        page_h = float(page.mediabox.height)
        rotation = int(page.rotation or 0)

        level_marks = []
        roof_labels = []
        cotas_altura = []
        raw_lines = []
        capas_dict = {}

        min_x, min_y = float("inf"), float("inf")
        max_x, max_y = float("-inf"), float("-inf")

        for pi, page_obj in enumerate(doc):
            pw = float(page_obj.mediabox.width)
            ph = float(page_obj.mediabox.height)
            rot = int(page_obj.rotation or 0)

            for b in page_obj.get_text('blocks'):
                txt = b[4].strip()
                if not txt:
                    continue
                cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
                mx, my = rotate_point(cx, cy, pw, ph, rot)

                for val in parse_levels(txt):
                    level_marks.append({'value': val, 'x': mx, 'y': my, 'page': pi})
                    cotas_altura.append({
                        "texto": txt,
                        "valor": val,
                        "posicion": (mx, my),
                        "layer": "TEXT_COTAS"
                    })

                if 'CUBIERTA' in txt.upper():
                    sm = SLOPE_RE.search(txt)
                    roof_labels.append({
                        'text': txt[:250],
                        'x': mx,
                        'y': my,
                        'slope_percent': float(sm.group(1).replace(',', '.')) if sm else None,
                        'page': pi,
                    })

            for di, d in enumerate(page_obj.get_drawings()):
                color = d.get('color')
                color_hex = f"#{int(color[0]*255):02x}{int(color[1]*255):02x}{int(color[2]*255):02x}" if color else "#1a6dba"
                stroke_width = d.get("width", 1.0)
                layer_name = f"Capa_Color_{color_hex}_w{stroke_width}"

                if layer_name not in capas_dict:
                    capas_dict[layer_name] = {
                        "name": layer_name,
                        "color": color_hex,
                        "stroke_width": stroke_width,
                        "is_off": False
                    }

                for si, item in enumerate(d.get('items', [])):
                    if item[0] == 'l':
                        a, b_pt = item[1], item[2]
                        raw_lines.append({
                            "start": (a.x, a.y),
                            "end": (b_pt.x, b_pt.y),
                            "inicio": (a.x, a.y),
                            "fin": (b_pt.x, b_pt.y),
                            "layer": layer_name,
                            "color": color_hex
                        })
                        for pt in (a, b_pt):
                            min_x, max_x = min(min_x, pt.x), max(max_x, pt.x)
                            min_y, max_y = min(min_y, pt.y), max(max_y, pt.y)

                    elif item[0] == 're':
                        r = item[1]
                        r_pts = [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)]
                        for rx, ry in r_pts:
                            min_x, max_x = min(min_x, rx), max(max_x, rx)
                            min_y, max_y = min(min_y, ry), max(max_y, ry)
                        for j in range(4):
                            a_pt, b_pt = r_pts[j], r_pts[(j + 1) % 4]
                            raw_lines.append({
                                "start": a_pt,
                                "end": b_pt,
                                "inicio": a_pt,
                                "fin": b_pt,
                                "layer": layer_name,
                                "color": color_hex
                            })

        model_meta = {
            'units': 'pdf-points',
            'pages': len(doc),
            'rotation': rotation,
            'page_size': [page_w, page_h],
            'levels': sorted(set(round(x['value'], 3) for x in level_marks)),
            'level_marks': level_marks,
            'roof_labels': roof_labels,
        }

        # Run Shapely polygonization
        pdf_bytes = file_bytes
        if not pdf_bytes:
            pdf_bytes = doc.tobytes()

        roof_regions = detect_roof_regions(pdf_bytes, model_meta)

        if min_x == float("inf"):
            rect = page.rect
            min_x, max_x = rect.x0, rect.x1
            min_y, max_y = rect.y0, rect.y1

        return {
            "capas": list(capas_dict.values()),
            "poligonos": roof_regions,
            "roof_regions": roof_regions,
            "lineas": raw_lines,
            "cotas_altura": cotas_altura,
            "level_marks": level_marks,
            "roof_labels": roof_labels,
            "lines_count": len(raw_lines),
            "bounding_box": {
                "min_x": min_x,
                "max_x": max_x,
                "min_y": min_y,
                "max_y": max_y,
                "width": max_x - min_x,
                "depth": max_y - min_y,
            }
        }
