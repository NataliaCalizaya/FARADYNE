import math
import logging
import os
import io  # agregar al tope del archivo si no está

import tempfile
from collections import defaultdict
from typing import Any, Dict, List, Tuple

import ezdxf
from ezdxf import recover
from ezdxf.document import Drawing
from shapely.geometry import LineString
from shapely.ops import polygonize_full, unary_union

from app.services.niveles_utils import NivelesUtils
from app.services.pdf_interpreter_service import PDFInterpreterService as _PDF

logger = logging.getLogger("faradyne.dxf")

Punto = Tuple[float, float]
Segmento = Tuple[Punto, Punto]

class DXFInterpreterService:
    """
    Interpreta planos DXF para FARADYNE.

    Reutiliza las MISMAS convenciones de capas (ROOF, AUX_ROOF, LEVELS,
    COTAS) y el MISMO formato de Modelo2D que PDFInterpreterService,
    delegando en él la clasificación de capas y el parseo de niveles,
    y en NivelesUtils la asociación nivel <-> lado de polígono. Así el
    resto del sistema (EditorModelo2DService, model3d_generator_service,
    mástiles, GeometriaViewer) no necesita saber si el plano vino de un
    DXF o de un PDF.

    Diferencia clave con el PDF: DXF ya trae geometría estructurada
    (polilíneas cerradas, capas nativas, coordenadas reales), así que:
      - los polígonos ROOF que ya llegan como polilínea cerrada se usan
        tal cual (no se reconstruyen con polygonize);
      - la escala se resuelve con la unidad real del dibujo ($INSUNITS),
        no con una heurística de texto de cota.
    """

    ROOF_MIN_AREA = _PDF.ROOF_MIN_AREA
    LEVEL_DEDUP_DISTANCE = _PDF.LEVEL_DEDUP_DISTANCE

    # Códigos $INSUNITS de DXF/AutoCAD -> factor a metros.
    # 0 (sin unidades) y cualquier código no contemplado -> se asume metros.
    # _INSUNITS_A_METROS = {
    #     1: 0.0254,   # pulgadas
    #     2: 0.3048,   # pies
    #     4: 0.001,    # milímetros
    #     5: 0.01,     # centímetros
    #     6: 1.0,      # metros
    #     10: 0.9144,  # yardas
    # }

    # =========================================================
    # VALIDACIÓN
    # =========================================================


# ...

    @staticmethod
    def validate_and_read_dxf(file_bytes: bytes, filename: str) -> Drawing:
        """
        Valida y carga un DXF, sea ASCII o Binario.

        ezdxf.readfile() soporta ambos formatos y detecta el encoding
        automáticamente, pero requiere un path real en disco (no un stream
        en memoria), por eso el archivo se vuelca primero a un temporal.
        """
        if not file_bytes:
            raise ValueError(f"El archivo DXF '{filename}' está vacío.")

        suffix = os.path.splitext(filename)[1] or ".dxf"
        tmp_path = None

        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            try:
                return ezdxf.readfile(tmp_path)

            except ezdxf.DXFStructureError:
                # El archivo tiene errores de estructura (frecuente en DXF
                # exportados por programas de terceros): intento de recuperación
                # en vez de rechazarlo directo.
                doc, auditor = recover.readfile(tmp_path)
                if auditor.has_errors:
                    logger.warning(
                        f"DXF '{filename}' recuperado con errores menores: "
                        f"{[e.message for e in auditor.errors]}"
                    )
                return doc

        except Exception as e:
            logger.error(f"No se pudo parsear DXF {filename}: {e}")
            raise ValueError(
                f"El archivo DXF '{filename}' está corrupto o tiene un formato "
                f"no soportado. Detalle: {e}"
            )

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    # =========================================================
    # ESCALA
    # =========================================================

    @classmethod
    def _factor_a_metros(cls, doc: Drawing) -> float:
        """
        Supuesto académico de FARADYNE (igual que en PDFInterpreterService):
        1 unidad de dibujo del DXF = 1 metro real.

        NO se usa $INSUNITS como factor de conversión porque en la práctica
        ese header casi nunca refleja la intención real de quien dibujó
        (muchos templates de AutoCAD lo dejan en milímetros por defecto
        aunque el plano se haya trazado pensando en metros). Se lo deja
        solo como advertencia de diagnóstico si contradice el supuesto.
        """
        try:
            insunits = int(doc.header.get("$INSUNITS", 0) or 0)
            if insunits not in (0, 6):  # 0 = sin unidades, 6 = metros
                logger.warning(
                    f"El DXF declara $INSUNITS={insunits} (no metros/sin unidades), "
                    "pero se interpreta igual como 1 unidad = 1 metro por "
                    "convención de FARADYNE. Verificar si el plano está mal escalado."
                )
        except Exception:
            pass

        return 1.0

    @staticmethod
    def _punto_a_metros(
        x: float, y: float, factor: float, origen_x: float, origen_y: float,
    ) -> Dict[str, float]:
        """
        A diferencia del PDF, en DXF el eje Y ya crece "hacia arriba":
        no hace falta invertirlo.
        """
        # return {
        #     "x": (float(x) - origen_x) * factor,
        #     "y": (-float(y) - origen_y) * factor,
        # }
        x0 = float(x) - origen_x
        y0 = float(y) - origen_y

        return {
            "x": -y0 * factor,
            "y": x0 * factor,
        }

    # =========================================================
    # CONSTRUCCIÓN DE POLÍGONOS
    # =========================================================

    @staticmethod
    def _nuevo_poligono(id_: str, capa: str, coords: List[Punto]) -> Dict[str, Any]:
        xs = [p[0] for p in coords]
        ys = [p[1] for p in coords]

        # Área por fórmula de shoelace (sin depender de shapely acá).
        area = 0.0
        for i in range(len(coords)):
            x1, y1 = coords[i]
            x2, y2 = coords[(i + 1) % len(coords)]
            area += x1 * y2 - x2 * y1
        area = abs(area) / 2.0

        return {
            "id": id_,
            "tipo": "poligono",
            "capa": capa or "ROOF",
            "origen": "dxf",
            "page": 0,
            "puntos": [{"x": x, "y": y} for x, y in coords],
            "area": area,
            "bounding_box": {
                "min_x": min(xs), "min_y": min(ys),
                "max_x": max(xs), "max_y": max(ys),
            },
            "centro": {"x": sum(xs) / len(xs), "y": sum(ys) / len(ys)},
            "niveles": [],
            "nivel_bajo": None,
            "nivel_medio": None,
            "nivel_alto": None,
            "pendiente": None,
            "tipo_cubierta": "pendiente_por_resolver",
        }

    @classmethod
    def _poligonos_desde_segmentos(
        cls,
        roof_segmentos: Dict[int, List[Segmento]],
        contador_inicial: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Reconstruye polígonos a partir de bordes ROOF sueltos (LINEs o
        polilíneas abiertas), reutilizando el mismo cierre de huecos y
        polygonize que usa el PDF (_cerrar_huecos + shapely).
        """
        poligonos = []
        contador = contador_inicial

        for _page, segmentos in roof_segmentos.items():
            if not segmentos:
                continue

            cerrados, _conectores = _PDF._cerrar_huecos(segmentos)

            try:
                piezas = [LineString(s) for s in cerrados]
                unido = unary_union(piezas)
                lista = list(unido.geoms) if hasattr(unido, "geoms") else [unido]
                caras, *_resto = polygonize_full(lista)
            except Exception:
                continue

            for cara in caras.geoms:
                if cara.is_empty or float(cara.area) < cls.ROOF_MIN_AREA:
                    continue

                coords = [(float(x), float(y)) for x, y in cara.exterior.coords[:-1]]
                coords = _PDF._limpiar_colineales(coords)

                if len(coords) < 3:
                    continue

                contador += 1
                poligonos.append(cls._nuevo_poligono(f"roof_{contador:03d}", "ROOF", coords))

        return poligonos

    # =========================================================
    # EXTRACCIÓN DE ENTIDADES
    # =========================================================

    @classmethod
    def _extraer_entidades(cls, msp) -> Dict[str, Any]:
        lineas: List[Dict[str, Any]] = []
        roof_segmentos: Dict[int, List[Segmento]] = defaultdict(list)
        aux_roof: List[Dict[str, Any]] = []
        poligonos_directos: List[Tuple[str, List[Punto]]] = []
        niveles_detectados: List[Dict[str, Any]] = []
        capas_detectadas: set = set()

        def _agregar_nivel(texto: str, x: float, y: float, capa: str) -> None:
            valor = _PDF._parse_level_text(
                texto, en_capa_niveles=_PDF._is_level_layer(capa)
            )
            if valor is None:
                return

            for nivel in niveles_detectados:
                if (
                    abs(nivel["valor"] - valor) < 1e-9
                    and math.hypot(nivel["x"] - x, nivel["y"] - y) < cls.LEVEL_DEDUP_DISTANCE
                ):
                    return  # duplicado

            niveles_detectados.append(
                _PDF._create_level(
                    level_id=f"dxf-nivel-{len(niveles_detectados) + 1:03d}",
                    value=valor,
                    text=texto,
                    x=x,
                    y=y,
                    page=0,
                    layer=capa or "LEVELS",
                )
            )

        for entity in msp:
            capa = _PDF._normalize_layer(entity.dxf.layer)
            if capa:
                capas_detectadas.add(capa)

            dxftype = entity.dxftype()

            # ---- Polilíneas: polígonos ROOF o simples líneas ----
            if dxftype in ("LWPOLYLINE", "POLYLINE"):
                try:
                    if dxftype == "LWPOLYLINE":
                        puntos = [(float(p[0]), float(p[1])) for p in entity.get_points()]
                        cerrada = bool(entity.is_closed)
                    else:
                        puntos = [
                            (float(v.dxf.location.x), float(v.dxf.location.y))
                            for v in entity.vertices
                        ]
                        cerrada = bool(entity.is_closed)
                except Exception as ex:
                    logger.debug(f"Error parseando polilínea: {ex}")
                    continue

                if len(puntos) < 2:
                    continue

                es_roof = _PDF._is_roof_layer(capa)
                es_aux_roof = _PDF._is_aux_roof_layer(capa)

                if es_roof and cerrada and len(puntos) >= 3:
                    # Ya es un polígono válido: se usa directo, sin polygonize.
                    poligonos_directos.append((capa, puntos))
                    continue

                aristas = list(
                    zip(puntos, puntos[1:] + ([puntos[0]] if cerrada else []))
                )

                for a, b in aristas:
                    if es_roof:
                        roof_segmentos[0].append((a, b))
                    elif es_aux_roof:
                        aux_roof.append({
                            "id": f"aux_roof_{len(aux_roof) + 1:04d}",
                            "tipo": "linea_pendiente",
                            "capa": capa or "AUX_ROOF",
                            "page": 0,
                            "x1": a[0], "y1": a[1], "x2": b[0], "y2": b[1],
                        })

                    lineas.append({
                        "x1": a[0], "y1": a[1], "x2": b[0], "y2": b[1],
                        "page": 0, "capa": capa,
                    })

            # ---- Líneas simples ----
            elif dxftype == "LINE":
                a = (float(entity.dxf.start.x), float(entity.dxf.start.y))
                b = (float(entity.dxf.end.x), float(entity.dxf.end.y))

                if _PDF._is_roof_layer(capa):
                    roof_segmentos[0].append((a, b))
                elif _PDF._is_aux_roof_layer(capa):
                    aux_roof.append({
                        "id": f"aux_roof_{len(aux_roof) + 1:04d}",
                        "tipo": "linea_pendiente",
                        "capa": capa or "AUX_ROOF",
                        "page": 0,
                        "x1": a[0], "y1": a[1], "x2": b[0], "y2": b[1],
                    })

                lineas.append({
                    "x1": a[0], "y1": a[1], "x2": b[0], "y2": b[1],
                    "page": 0, "capa": capa,
                })

            # ---- Texto: detección de niveles (misma lógica que el PDF) ----
            elif dxftype in ("TEXT", "MTEXT"):
                texto = (entity.dxf.text if dxftype == "TEXT" else entity.text) or ""
                texto = texto.strip()
                if not texto:
                    continue

                if _PDF._is_dimension_layer(capa):
                    continue  # las cotas de medida no son niveles

                try:
                    insert = entity.dxf.insert
                    x, y = float(insert.x), float(insert.y)
                except Exception:
                    continue

                _agregar_nivel(texto, x, y, capa)

        return {
            "lineas": lineas,
            "roof_segmentos": roof_segmentos,
            "aux_roof": aux_roof,
            "poligonos_directos": poligonos_directos,
            "niveles_detectados": niveles_detectados,
            "capas_detectadas": capas_detectadas,
        }

    # =========================================================
    # INTERPRETACIÓN PRINCIPAL
    # =========================================================

    @classmethod
    def interpret_dxf_data(cls, doc: Drawing) -> Dict[str, Any]:
        """Extrae capas, polígonos ROOF, niveles asociados y líneas de un DXF,
        en el mismo formato de Modelo2D que produce PDFInterpreterService."""
        msp = doc.modelspace()

        layers_info = [
            {"name": layer.dxf.name, "color": layer.dxf.color, "is_off": layer.is_off()}
            for layer in doc.layers
        ]

        extraido = cls._extraer_entidades(msp)

        # ---- Polígonos: directos (cerrados) + reconstruidos desde bordes sueltos ----
        poligonos: List[Dict[str, Any]] = []
        contador = 0
        for capa, puntos in extraido["poligonos_directos"]:
            contador += 1
            poligonos.append(cls._nuevo_poligono(f"roof_{contador:03d}", capa, puntos))

        poligonos.extend(
            cls._poligonos_desde_segmentos(extraido["roof_segmentos"], contador)
        )

        # ---- Niveles: asociación automática a lados de polígono (NO TOCAR) ----
        niveles, descartados = NivelesUtils.asociar_niveles_automaticamente(
            poligonos,
            extraido["niveles_detectados"],
            NivelesUtils.DISTANCIA_MAXIMA_LADO,
        )
        NivelesUtils.reconstruir_niveles_poligonos(poligonos, niveles)

        # ---- Bounding box en unidades nativas del DXF ----
        lineas = extraido["lineas"]
        if lineas:
            xs = [l["x1"] for l in lineas] + [l["x2"] for l in lineas]
            ys = [l["y1"] for l in lineas] + [l["y2"] for l in lineas]
            bbox_nativo = {
                "min_x": min(xs), "min_y": min(ys),
                "max_x": max(xs), "max_y": max(ys),
            }
        else:
            bbox_nativo = {"min_x": 0.0, "min_y": 0.0, "max_x": 20.0, "max_y": 15.0}

        # ---- Conversión a metros según la unidad real del dibujo ----
        factor = cls._factor_a_metros(doc)
        origen_x, origen_y = bbox_nativo["min_x"], bbox_nativo["min_y"]

        def conv(x: float, y: float) -> Dict[str, float]:
            return cls._punto_a_metros(x, y, factor, origen_x, origen_y)

        lineas_m = []
        for l in lineas:
            p1, p2 = conv(l["x1"], l["y1"]), conv(l["x2"], l["y2"])
            lineas_m.append({**l, "x1": p1["x"], "y1": p1["y"], "x2": p2["x"], "y2": p2["y"]})

        aux_roof_m = []
        for l in extraido["aux_roof"]:
            p1, p2 = conv(l["x1"], l["y1"]), conv(l["x2"], l["y2"])
            aux_roof_m.append({**l, "x1": p1["x"], "y1": p1["y"], "x2": p2["x"], "y2": p2["y"]})

        poligonos_m = []
        for p in poligonos:
            puntos_m = [conv(pt["x"], pt["y"]) for pt in p["puntos"]]
            xs = [pt["x"] for pt in puntos_m]
            ys = [pt["y"] for pt in puntos_m]
            poligonos_m.append({
                **p,
                "puntos": puntos_m,
                "area": p["area"] * factor * factor,
                "bounding_box": {
                    "min_x": min(xs), "min_y": min(ys),
                    "max_x": max(xs), "max_y": max(ys),
                },
                "centro": {"x": sum(xs) / len(xs), "y": sum(ys) / len(ys)},
            })

        niveles_m = []
        for n in niveles:
            p = conv(n["x"], n["y"])
            niveles_m.append({**n, "x": p["x"], "y": p["y"], "posicion": p})

        # bbox_min_m = conv(bbox_nativo["min_x"], bbox_nativo["min_y"])
        # bbox_max_m = conv(bbox_nativo["max_x"], bbox_nativo["max_y"])
        # bounding_box_m = {
        #     "min_x": bbox_min_m["x"], "min_y": bbox_min_m["y"],
        #     "max_x": bbox_max_m["x"], "max_y": bbox_max_m["y"],
        #     "width": bbox_max_m["x"] - bbox_min_m["x"],
        #     "depth": bbox_max_m["y"] - bbox_min_m["y"],
        # }

        # Reemplazar el bloque actual de bbox_min_m/bbox_max_m/bounding_box_m por:
        if lineas_m:
            xs_m = [l["x1"] for l in lineas_m] + [l["x2"] for l in lineas_m]
            ys_m = [l["y1"] for l in lineas_m] + [l["y2"] for l in lineas_m]
            bounding_box_m = {
                "min_x": min(xs_m), "min_y": min(ys_m),
                "max_x": max(xs_m), "max_y": max(ys_m),
                "width": max(xs_m) - min(xs_m),
                "depth": max(ys_m) - min(ys_m),
            }
        else:
            bounding_box_m = {"min_x": 0.0, "min_y": 0.0, "max_x": 20.0, "max_y": 15.0, "width": 20.0, "depth": 15.0}

        modelo = {
            "version": "0.5.0",
            "units": "meters",
            "coordinate_system": "dxf-native",
            "pages": 1,
            "capas": sorted(extraido["capas_detectadas"]),
            "lineas": lineas_m,
            "roof_lines": [],
            "aux_roof": aux_roof_m,
            "poligonos": poligonos_m,
            "niveles": niveles_m,
            "cotas_altura": niveles_m,
            "niveles_descartados": descartados[:500],
            "level_marks": niveles_m,
            "textos": [],
            "bounding_box": bounding_box_m,
            "scale": {
                "factor_xy": factor,
                "source": "dxf_insunits",
                "confianza": "unidad_dxf",
            },
        }

        modelo["resumen"] = {
            "cantidad_lineas": len(modelo["lineas"]),
            "cantidad_poligonos_roof": len(modelo["poligonos"]),
            "cantidad_niveles_detectados": len(extraido["niveles_detectados"]),
            "cantidad_niveles": len(modelo["niveles"]),
            "cantidad_niveles_descartados": len(descartados),
            "unidad_geometria": "metros",
            "factor_escala_xy": factor,
            "origen_coordenadas": "bounding_box",
        }

        return modelo