import io
import logging
from typing import Any, Dict, List, Tuple
import ezdxf
from ezdxf.document import Drawing

logger = logging.getLogger("faradyne.dxf")


class DXFInterpreterService:
    """Service to parse, validate and interpret DXF drawings using ezdxf."""

    @staticmethod
    def validate_and_read_dxf(file_bytes: bytes, filename: str) -> Drawing:
        """Validate DXF file integrity and load into ezdxf Document.
        Raises ValueError if corrupted or unsupported format.
        """
        try:
            stream = io.StringIO(file_bytes.decode("utf-8", errors="ignore"))
            doc = ezdxf.read(stream)
            return doc
        except Exception as e:
            logger.warning(f"ASCII DXF parse failed for {filename}, trying binary decode: {e}")
            try:
                # Retry binary stream read if ascii failed
                stream_bin = io.BytesIO(file_bytes)
                doc = ezdxf.read(stream_bin)
                return doc
            except Exception as bin_err:
                logger.error(f"Failed to parse DXF file {filename}: {bin_err}")
                raise ValueError(
                    f"El archivo DXF '{filename}' está corrupto o tiene un formato no soportado. Detalle: {str(bin_err)}"
                )

    @staticmethod
    def interpret_dxf_data(doc: Drawing) -> Dict[str, Any]:
        """Extract layers, closed 2D polygons, elevation quotes, and 3D faces from ezdxf document."""
        msp = doc.modelspace()

        layers_info = []
        for layer in doc.layers:
            layers_info.append({
                "name": layer.dxf.name,
                "color": layer.dxf.color,
                "is_off": layer.is_off(),
            })

        polygons = []
        cotas_altura = []
        entities_3d = []
        raw_lines = []

        min_x, min_y = float("inf"), float("inf")
        max_x, max_y = float("-inf"), float("-inf")

        for entity in msp:
            layer_name = entity.dxf.layer

            # 1. Closed Polygons (LWPOLYLINE / POLYLINE)
            if entity.dxftype() in ("LWPOLYLINE", "POLYLINE"):
                try:
                    if entity.dxftype() == "LWPOLYLINE":
                        points = [(p[0], p[1]) for p in entity.get_points()]
                        is_closed = entity.is_closed
                    else:
                        points = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
                        is_closed = entity.is_closed

                    if len(points) >= 3:
                        for px, py in points:
                            min_x, max_x = min(min_x, px), max(max_x, px)
                            min_y, max_y = min(min_y, py), max(max_y, py)

                        # Look for layer-based elevation tag (e.g. 'CUBIERTA_7.90')
                        cota = 3.0  # default height
                        if "_" in layer_name:
                            try:
                                possible_cota = float(layer_name.split("_")[-1].replace("m", "").replace(",", "."))
                                cota = possible_cota
                            except ValueError:
                                pass

                        polygons.append({
                            "layer": layer_name,
                            "is_closed": is_closed,
                            "points": points,
                            "cota_base": 0.0,
                            "cota_superior": cota,
                            "pendiente": 0.0 if "inclinad" not in layer_name.lower() else 15.0,  # 15% slope if layer specifies
                        })
                except Exception as ex:
                    logger.debug(f"Error parsing polyline entity: {ex}")

            # 2. Simple Lines
            elif entity.dxftype() == "LINE":
                p1 = (entity.dxf.start.x, entity.dxf.start.y)
                p2 = (entity.dxf.end.x, entity.dxf.end.y)
                raw_lines.append({"start": p1, "end": p2, "layer": layer_name})

                for px, py in (p1, p2):
                    min_x, max_x = min(min_x, px), max(max_x, px)
                    min_y, max_y = min(min_y, py), max(max_y, py)

            # 3. Text / Heights / Cotas
            elif entity.dxftype() in ("TEXT", "MTEXT"):
                text_content = entity.dxf.text if entity.dxftype() == "TEXT" else entity.text
                if "+" in text_content or "NIVEL" in text_content.upper() or "NPT" in text_content.upper():
                    try:
                        clean_str = text_content.replace("NPT", "").replace("NIVEL", "").replace("+", "").replace("m", "").strip()
                        val = float(clean_str)
                        cotas_altura.append({
                            "texto": text_content,
                            "valor": val,
                            "posicion": (entity.dxf.insert.x if hasattr(entity.dxf, 'insert') else 0.0,
                                         entity.dxf.insert.y if hasattr(entity.dxf, 'insert') else 0.0),
                            "layer": layer_name
                        })
                    except ValueError:
                        pass

            # 4. Native 3D entities (3DFACE, MESH, POLYFACE)
            elif entity.dxftype() == "3DFACE":
                v1 = (entity.dxf.vtx0.x, entity.dxf.vtx0.y, entity.dxf.vtx0.z)
                v2 = (entity.dxf.vtx1.x, entity.dxf.vtx1.y, entity.dxf.vtx1.z)
                v3 = (entity.dxf.vtx2.x, entity.dxf.vtx2.y, entity.dxf.vtx2.z)
                v4 = (entity.dxf.vtx3.x, entity.dxf.vtx3.y, entity.dxf.vtx3.z)
                entities_3d.append({
                    "type": "3DFACE",
                    "vertices": [v1, v2, v3, v4],
                    "layer": layer_name
                })

        # Provide a default bounding box polygon if no closed polylines were found
        if not polygons and min_x < max_x and min_y < max_y:
            polygons.append({
                "layer": "Perimetro_Default",
                "is_closed": True,
                "points": [(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)],
                "cota_base": 0.0,
                "cota_superior": 6.0,
                "pendiente": 0.0,
            })

        if min_x == float("inf"):
            min_x, max_x, min_y, max_y = 0.0, 20.0, 0.0, 15.0

        return {
            "capas": layers_info,
            "poligonos": polygons,
            "cotas_altura": cotas_altura,
            "entities_3d": entities_3d,
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
