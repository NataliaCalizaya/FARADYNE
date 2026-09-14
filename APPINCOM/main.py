from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union, polygonize
from shapely.affinity import affine_transform
import fitz
import ezdxf
import io
import re
import math

app = FastAPI(title='FARADYNE API', version='0.3.1')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

LEVEL_RE = re.compile(r'\+\s*(\d+(?:[.,]\d+)?)')
SLOPE_RE = re.compile(r'PEND\.?\s*(\d+(?:[.,]\d+)?)\s*%', re.I)


def parse_levels(text: str):
    out = []
    for m in LEVEL_RE.finditer(text or ''):
        try:
            v = float(m.group(1).replace(',', '.'))
            if 0 <= v <= 100:
                out.append(v)
        except ValueError:
            pass
    return sorted(set(out))


def rotate_point(x, y, page_w, page_h, rotation):
    # PyMuPDF devuelve la geometría en coordenadas del mediabox sin aplicar
    # visualmente la rotación. La planta de este PDF está rotada 270°.
    r = rotation % 360
    if r == 90:
        return page_h - y, x
    if r == 180:
        return page_w - x, page_h - y
    if r == 270:
        return y, page_w - x
    return x, y


def drawing_lines(page, wanted_color=None):
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


def extract(data: bytes):
    doc = fitz.open(stream=data, filetype='pdf')
    els = []
    level_marks = []
    roof_labels = []

    for pi, page in enumerate(doc):
        page_w = float(page.mediabox.width)
        page_h = float(page.mediabox.height)
        rotation = int(page.rotation or 0)

        for b in page.get_text('blocks'):
            txt = b[4].strip()
            if not txt:
                continue
            cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            mx, my = rotate_point(cx, cy, page_w, page_h, rotation)
            for value in parse_levels(txt):
                level_marks.append({'value': value, 'x': mx, 'y': my, 'page': pi})
            if 'CUBIERTA' in txt.upper():
                sm = SLOPE_RE.search(txt)
                roof_labels.append({
                    'text': txt[:250],
                    'x': mx,
                    'y': my,
                    'slope_percent': float(sm.group(1).replace(',', '.')) if sm else None,
                    'page': pi,
                })

        for di, d in enumerate(page.get_drawings()):
            color = d.get('color')
            color_arr = list(color) if color else None
            for si, item in enumerate(d.get('items', [])):
                if item[0] == 'l':
                    a, b = item[1], item[2]
                    els.append({
                        'id': f'p{pi}-d{di}-s{si}', 'type': 'line',
                        'x1': a.x, 'y1': a.y, 'x2': b.x, 'y2': b.y,
                        'page': pi, 'confidence': .98, 'color': color_arr,
                    })
                elif item[0] == 're':
                    r = item[1]
                    pts = [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)]
                    for j in range(4):
                        a, b = pts[j], pts[(j + 1) % 4]
                        els.append({
                            'id': f'p{pi}-d{di}-r{si}-{j}', 'type': 'line',
                            'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1],
                            'page': pi, 'confidence': .96, 'color': color_arr,
                        })

    model = {
        'units': 'pdf-points',
        'pages': len(doc),
        'rotation': int(doc[0].rotation or 0) if len(doc) else 0,
        'page_size': [float(doc[0].mediabox.width), float(doc[0].mediabox.height)] if len(doc) else [0, 0],
        'levels': sorted(set(round(x['value'], 3) for x in level_marks)),
        'level_marks': level_marks,
        'roof_labels': roof_labels,
        'elements': els,
        'texts': [],
    }
    model['roof_regions'] = detect_roof_regions(data, model)
    return model


def to_model_geom(poly, page_size, rotation):
    page_w, page_h = page_size
    # affine_transform: x'=a*x+b*y+d ; y'=e*x+f*y+g
    r = rotation % 360
    if r == 270:
        return affine_transform(poly, [0, 1, -1, 0, 0, page_w])
    if r == 90:
        return affine_transform(poly, [0, -1, 1, 0, page_h, 0])
    if r == 180:
        return affine_transform(poly, [-1, 0, 0, -1, page_w, page_h])
    return poly


def detect_roof_regions(data: bytes, model: dict):
    doc = fitz.open(stream=data, filetype='pdf')
    page = doc[0]
    page_size = model['page_size']
    rotation = model['rotation']

    all_lines = drawing_lines(page)
    red_lines = drawing_lines(page, (1.0, 0.0, 0.0))
    if not all_lines:
        return []

    # El objetivo no es convertir cada línea del CAD en un sólido. Se buscan
    # regiones cerradas que representen cubiertas y se ignora la maraña de
    # cotas/hachurados.
    all_polys = list(polygonize(unary_union(all_lines)))
    red_polys = list(polygonize(unary_union(red_lines))) if red_lines else []
    bbox = unary_union(all_lines).bounds
    drawing_area = max(1.0, (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))

    candidates = []
    # En este plano, las líneas rojas delimitan claramente varias cubiertas.
    for p in red_polys:
        if p.area >= drawing_area * 0.010 and p.area <= drawing_area * 0.40:
            candidates.append(p)

    # Agregar la región grande de cubierta que contiene etiquetas de techo.
    roof_pts = [Point(x['x'], x['y']) for x in model['roof_labels']]
    for p in sorted(all_polys, key=lambda q: q.area, reverse=True):
        if p.area < drawing_area * 0.03 or p.area > drawing_area * 0.60:
            continue
        if any(p.contains(pt) for pt in roof_pts):
            candidates.append(p)
            break

    # Escala de referencia calculada sobre las cubiertas detectadas, no sobre
    # el cajetín/cotas del PDF. Esto permite interpretar correctamente 12%/20%.
    if candidates:
        cb = unary_union(candidates).bounds
        model_scale = 80.0 / max(cb[2] - cb[0], cb[3] - cb[1], 1.0)
    else:
        model_scale = 1.0

    # Deduplicación por IoU aproximada.
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
        # Reducimos el ruido de vértices sin deformar la forma general.
        geom = geom.simplify(1.5, preserve_topology=True)
        if geom.geom_type != 'Polygon' or geom.area < 1000:
            continue

        # Etiquetas y niveles cercanos a la región.
        labels = sorted(model['roof_labels'], key=lambda l: geom.distance(Point(l['x'], l['y'])))
        region_labels = [l for l in labels if geom.distance(Point(l['x'], l['y'])) < 120][:3]
        # Los textos de nivel pueden quedar dentro de una región grande aunque
        # pertenezcan a otra cubierta. Primero usamos los niveles próximos a
        # la etiqueta de cubierta de esa región; luego ampliamos la búsqueda.
        marks = [m for m in model['level_marks'] if geom.contains(Point(m['x'], m['y'])) or geom.distance(Point(m['x'], m['y'])) < 30]
        if region_labels:
            anchor = min(region_labels, key=lambda l: geom.distance(Point(l['x'], l['y'])))
            local = sorted(model['level_marks'], key=lambda m: math.hypot(m['x']-anchor['x'], m['y']-anchor['y']))[:6]
            marks = [m for m in local if m in marks or math.hypot(m['x']-anchor['x'], m['y']-anchor['y']) < 230]
        marks = sorted(marks, key=lambda m: math.hypot(m['x']-geom.centroid.x, m['y']-geom.centroid.y))[:6]
        if not marks:
            marks = sorted(model['level_marks'], key=lambda m: geom.distance(Point(m['x'], m['y'])))[:3]

        # Solo niveles distintos, manteniendo sus posiciones.
        seen = set(); lm = []
        for m in sorted(marks, key=lambda x: x['value']):
            key = (round(m['value'], 2), round(m['x'], 1), round(m['y'], 1))
            if key not in seen:
                seen.add(key); lm.append(m)

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
                    # PDF points -> metros usando la escala global de la planta.
                    qbbox = geom.bounds
                    # scale is assigned later; only ratios matter here.
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
            'levels': sorted(set(round(x['value'], 2) for x in lm)),
            'level_marks': [{'value': x['value'], 'x': x['x'], 'y': x['y']} for x in lm],
            'slope_percent': slope_target,
            'slope_pair': [
                {'value': chosen[0]['value'], 'x': chosen[0]['x'], 'y': chosen[0]['y']},
                {'value': chosen[1]['value'], 'x': chosen[1]['x'], 'y': chosen[1]['y']},
            ] if len(chosen) == 2 else [],
        })

    # Orden espacial para que el DXF y el visor resulten fáciles de leer.
    regions.sort(key=lambda r: (min(p[1] for p in r['footprint']), min(p[0] for p in r['footprint'])))
    return regions


def bbox_regions(regions):
    pts = [p for r in regions for p in r['footprint']]
    if not pts:
        return (0, 0, 80, 20)
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def scale_regions(regions):
    x0, y0, x1, y1 = bbox_regions(regions)
    w, h = max(1, x1 - x0), max(1, y1 - y0)
    # La planta se normaliza a una escala arquitectónica razonable.
    # Convención DXF: X/Y = planta y Z = altura. NO se gira aquí: la orientación
    # horizontal es una decisión de presentación del visor 2D/3D, no de la geometría.
    scale = 80.0 / max(w, h)
    out = []
    for r in regions:
        fp = [[(x - x0) * scale, (y1 - y) * scale] for x, y in r['footprint']]
        marks = [{'value': m['value'], 'x': (m['x'] - x0) * scale, 'y': (y1 - m['y']) * scale} for m in r['level_marks']]
        pair = [{'value': m['value'], 'x': (m['x'] - x0) * scale, 'y': (y1 - m['y']) * scale} for m in r.get('slope_pair', [])]
        out.append({**r, 'footprint': fp, 'level_marks': marks, 'slope_pair': pair})
    return out, (0, 0, (x1-x0)*scale, (y1-y0)*scale)


def top_plane(region):
    fp = region['footprint']
    levels = region.get('levels', [])
    pair = region.get('slope_pair', [])
    if len(pair) == 2:
        a, b = pair
        dx, dy = b['x'] - a['x'], b['y'] - a['y']
        den = dx*dx + dy*dy
        if den > 1e-9:
            # z = ax + by + c, con gradiente paralelo a la línea de máxima pendiente.
            dz = b['value'] - a['value']
            A = dz * dx / den
            B = dz * dy / den
            C = a['value'] - A*a['x'] - B*a['y']
            return lambda x, y: max(0.0, A*x + B*y + C), min(a['value'], b['value']), max(a['value'], b['value'])
    z = max(levels) if levels else 3.7
    return lambda x, y: z, z, z


def add_prism_with_roof(msp, region):
    fp = region['footprint']
    zfun, zlow, zhigh = top_plane(region)
    base = 0.0
    # Limpiar auto-intersecciones residuales del simplificado.
    poly = Polygon(fp).buffer(0)
    if poly.is_empty or poly.geom_type != 'Polygon':
        return
    pts = [(float(x), float(y)) for x, y in list(poly.exterior.coords)[:-1]]
    top = [(x, y, float(zfun(x, y))) for x, y in pts]
    bot = [(x, y, base) for x, y in pts]

    # Paredes laterales del volumen bajo la cubierta.
    for i in range(len(pts)):
        j = (i + 1) % len(pts)
        msp.add_3dface([bot[i], bot[j], top[j], top[i]], dxfattribs={'layer': 'SOPORTE'})

    # Superficie superior triangulada con fan; las regiones detectadas son simples.
    for i in range(1, len(top)-1):
        msp.add_3dface([top[0], top[i], top[i+1]], dxfattribs={'layer': 'CUBIERTA'})

    # Base (útil al abrir el DXF en CAD y para cerrar visualmente el sólido).
    for i in range(1, len(bot)-1):
        msp.add_3dface([bot[0], bot[i+1], bot[i]], dxfattribs={'layer': 'SOPORTE'})


def make3d(m):
    regions, model_bbox = scale_regions(m.get('roof_regions', []))
    if not regions:
        raise ValueError('No se encontraron regiones cerradas de cubierta para construir el modelo 3D.')

    doc = ezdxf.new('R2018')
    msp = doc.modelspace()
    for name in ['SOPORTE', 'CUBIERTA', 'NIVELES', 'TANQUE']:
        if name not in doc.layers:
            doc.layers.add(name)

    for region in regions:
        add_prism_with_roof(msp, region)

    # Tanque/elemento elevado: se coloca en la posición real del +9.30 detectado.
    tank = None
    high = [x for x in m.get('level_marks', []) if abs(x['value'] - 9.30) < .02]
    if high:
        x0, y0, x1, y1 = model_bbox
        # Reutilizamos la misma transformación que scale_regions.
        raw_minx, raw_miny, raw_maxx, raw_maxy = bbox_regions(m.get('roof_regions', []))
        w = max(1, raw_maxx-raw_minx); h=max(1,raw_maxy-raw_miny); scale=80/max(w,h)
        p = high[0]
        tx=(p['x']-raw_minx)*scale; ty=(raw_maxy-p['y'])*scale
        tw=max(2.0, (x1-x0)*.06); td=max(1.5, (y1-y0)*.06)
        z0=7.9; z1=9.3
        tank={'x':tx,'y':ty,'width':tw,'depth':td,'base':z0,'top':z1}
        q=[(tx-tw/2,ty-td/2,z0),(tx+tw/2,ty-td/2,z0),(tx+tw/2,ty+td/2,z0),(tx-tw/2,ty+td/2,z0),
           (tx-tw/2,ty-td/2,z1),(tx+tw/2,ty-td/2,z1),(tx+tw/2,ty+td/2,z1),(tx-tw/2,ty+td/2,z1)]
        for f in [(0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)]:
            msp.add_3dface([q[i] for i in f], dxfattribs={'layer':'TANQUE'})

    # Niveles reconocidos, ubicados donde aparecen en el plano.
    raw_regions=m.get('roof_regions', [])
    if raw_regions:
        raw_minx, raw_miny, raw_maxx, raw_maxy=bbox_regions(raw_regions)
        scale=80/max(1,raw_maxx-raw_minx,raw_maxy-raw_miny)
        for mark in m.get('level_marks', []):
            x=(mark['x']-raw_minx)*scale; y=(raw_maxy-mark['y'])*scale; z=mark['value']
            text=msp.add_text(f'+{z:.2f}',dxfattribs={'height':0.35,'layer':'NIVELES'})
            text.set_placement((x,y,z+0.05))

    s=io.StringIO(); doc.write(s)
    metadata={
        'levels': sorted(float(v) for v in m.get('levels', [])),
        'bbox': list(model_bbox),
        'regions': regions,
        'tank': tank,
        'region_count': len(regions),
    }
    return s.getvalue().encode(), metadata


@app.get('/api/health')
def health():
    return {'ok': True, 'service': 'faradyne-backend', 'version': '0.3.0'}


@app.post('/api/plano/extract')
async def api_extract(file: UploadFile = File(...)):
    data = await file.read()
    if not data:
        raise HTTPException(400, 'El archivo está vacío.')
    try:
        model = extract(data)
        model['source_file'] = file.filename
        return model
    except Exception as e:
        raise HTTPException(500, f'No se pudo procesar el PDF: {e}')


@app.post('/api/modelo/generar-3d-preview')
async def preview(m: dict):
    try:
        _, meta = make3d(m)
        return {'ok': True, 'metadata': meta}
    except Exception as e:
        raise HTTPException(500, f'No se pudo generar el modelo 3D: {e}')


@app.post('/api/modelo/generar-3d')
async def dxf(m: dict):
    try:
        data, _ = make3d(m)
        return Response(data, media_type='application/dxf', headers={
            'Content-Disposition': 'attachment; filename="faradyne_modelo_3d.dxf"'
        })
    except Exception as e:
        raise HTTPException(500, f'No se pudo generar el DXF 3D: {e}')
