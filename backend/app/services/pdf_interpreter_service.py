from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import pymupdf as fitz
except ImportError:
    import fitz

from shapely.geometry import LineString
from shapely.ops import polygonize_full, unary_union

from app.services.niveles_utils import NivelesUtils


Punto = Tuple[float, float]
Segmento = Tuple[Punto, Punto]


class PDFInterpreterService:
    """
    Interpreta planos PDF vectoriales para FARADYNE.

    El PDF se procesa inicialmente en las coordenadas nativas de PyMuPDF.
    Luego de construir y asociar los polígonos y niveles, el Modelo2D se
    convierte a metros para que X, Y y Z sean coherentes.

    Supuesto académico de FARADYNE:
        Una cota arquitectónica de 21.60 representa 21.60 metros reales.

    Flujo:
        PDF
          ↓
        extracción geométrica
          ↓
        detección de niveles
          ↓
        construcción de ROOF
          ↓
        asociación de niveles
          ↓
        cálculo de escala
          ↓
        conversión a metros
          ↓
        normalización del sistema de coordenadas
          ↓
        Modelo2D
    """

    # =========================================================
    # CONFIGURACIÓN
    # =========================================================

    ROOF_LAYER_PATTERN = re.compile(
        r"^(?:.*[|$])?ROOF[ _\-]?\d*$"
    )

    AUX_ROOF_LAYER_PATTERN = re.compile(
        r"^(?:.*[|$])?AUX[ _\-]?ROOF[ _\-]?\d*$"
    )

    LEVEL_LAYER_PATTERN = re.compile(
        r"^(?:.*[|$])?(?:LEVELS?|NIVELES)[ _\-]?\d*$"
    )

    LEVEL_SYMBOL_LAYER_PATTERN = re.compile(
        r"^(?:.*[|$])?(?:SIMBOL|SYMBOL|SIMBOLO)S?[ _\-]?"
        r"(?:LEVELS?|NIVELES)[ _\-]?\d*$"
    )

    DIMENSION_LAYER_PATTERN = re.compile(
        r"^(?:.*[|$])?(?:COTAS?|DIM|DIMENSIONS?|DIMENSIONES)"
        r"[ _\-]?\d*$"
    )

    LEVEL_TEXT_PATTERN = re.compile(
        r"^\s*([+\-±−–])?\s*(\d{1,3}(?:[.,]\d{1,3})?)"
        r"\s*(?:m|mts?)?\s*$",
        re.IGNORECASE,
    )

    LEVEL_EMBEDDED_PATTERN = re.compile(
        r"(?<![\w.,])([+\-±−–])\s*(\d{1,3}(?:[.,]\d{1,2})?)(?!\d)"
    )

    ROOF_SNAP_TOLERANCE = 0.05
    ROOF_GAP_TOLERANCE = 1.5
    ROOF_COLLINEAR_TOLERANCE = 0.02
    ROOF_MIN_AREA = 1.0
    CURVE_SEGMENTS = 12

    NIVEL_DISTANCIA_MAXIMA = NivelesUtils.DISTANCIA_MAXIMA_LADO
    LEVEL_DEDUP_DISTANCE = 2.0

    # ---------------------------------------------------------
    # ESCALA
    # ---------------------------------------------------------

    # Factor mínimo y máximo razonables:
    # metros / punto PDF.
    SCALE_FACTOR_MIN = 0.00001
    SCALE_FACTOR_MAX = 100.0

    # Distancia máxima entre el texto de una cota y su línea.
    DIMENSION_TEXT_MAX_DISTANCE = 100.0

    # Si una referencia se aleja demasiado de la mediana,
    # se considera una referencia poco confiable.
    SCALE_OUTLIER_TOLERANCE = 0.20

    # =========================================================
    # CAPAS
    # =========================================================

    @staticmethod
    def _normalize_layer(layer: Any) -> str:
        """Normaliza el nombre de una capa."""
        if layer is None:
            return ""

        return re.sub(
            r"\s+",
            " ",
            str(layer).strip().upper(),
        )

    @classmethod
    def _is_roof_layer(cls, layer: str) -> bool:
        return bool(cls.ROOF_LAYER_PATTERN.match(layer))

    @classmethod
    def _is_aux_roof_layer(cls, layer: str) -> bool:
        return bool(cls.AUX_ROOF_LAYER_PATTERN.match(layer))

    @classmethod
    def _is_level_layer(cls, layer: str) -> bool:
        return bool(cls.LEVEL_LAYER_PATTERN.match(layer))

    @classmethod
    def _is_level_symbol_layer(cls, layer: str) -> bool:
        return bool(cls.LEVEL_SYMBOL_LAYER_PATTERN.match(layer))

    @classmethod
    def _is_dimension_layer(cls, layer: str) -> bool:
        return bool(cls.DIMENSION_LAYER_PATTERN.match(layer))

    @staticmethod
    def _point_dict(
        x: float,
        y: float,
    ) -> Dict[str, float]:
        return {
            "x": float(x),
            "y": float(y),
        }

    # =========================================================
    # COTAS / ESCALA
    # =========================================================

    @classmethod
    def _parse_dimension_value(
        cls,
        text: str,
    ) -> Optional[float]:
        """
        Extrae una longitud expresada en metros.

        Ejemplos:
            21.60
            21,60
            8.50 m
            8,50 mts
        """
        if not text:
            return None

        clean = text.strip().replace(",", ".")

        match = re.fullmatch(
            r"\s*(\d+(?:\.\d+)?)\s*(?:m|mts?)?\s*",
            clean,
            re.IGNORECASE,
        )

        if not match:
            return None

        try:
            value = float(match.group(1))
        except ValueError:
            return None

        if value <= 0:
            return None

        return value

    @classmethod
    def _obtener_lineas_cotas(
        cls,
        lineas: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Obtiene las líneas pertenecientes a capas de cotas."""
        return [
            linea
            for linea in lineas
            if cls._is_dimension_layer(
                cls._normalize_layer(linea.get("capa"))
            )
        ]

    @classmethod
    def _distancia_punto_segmento(
        cls,
        px: float,
        py: float,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
    ) -> float:
        """Calcula la distancia entre un punto y un segmento."""
        dx = x2 - x1
        dy = y2 - y1

        if dx == 0 and dy == 0:
            return math.hypot(
                px - x1,
                py - y1,
            )

        t = (
            (px - x1) * dx
            + (py - y1) * dy
        ) / (dx * dx + dy * dy)

        t = max(
            0.0,
            min(1.0, t),
        )

        cx = x1 + t * dx
        cy = y1 + t * dy

        return math.hypot(
            px - cx,
            py - cy,
        )

    @classmethod
    def _calcular_mediana(
        cls,
        valores: List[float],
    ) -> float:
        """Calcula la mediana de una lista."""
        ordenados = sorted(valores)

        if not ordenados:
            return 1.0

        mitad = len(ordenados) // 2

        if len(ordenados) % 2:
            return ordenados[mitad]

        return (
            ordenados[mitad - 1]
            + ordenados[mitad]
        ) / 2.0

    @classmethod
    def _detectar_factor_escala(
        cls,
        lineas: List[Dict[str, Any]],
        textos: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Detecta el factor de conversión:

            metros / punto PDF

        utilizando cotas del plano.

        Ejemplo:

            Cota real = 21.60 m
            Línea PDF = 612.34 puntos

            factor = 21.60 / 612.34

        Se utilizan varias cotas cuando están disponibles y se toma
        la mediana para reducir errores de detección.
        """

        lineas_cotas = cls._obtener_lineas_cotas(lineas)

        if not lineas_cotas:
            return {
                "factor_xy": 1.0,
                "source": "default",
                "referencias": [],
                "confianza": "sin_cotas",
            }

        factores: List[float] = []
        referencias: List[Dict[str, Any]] = []

        for texto in textos:
            capa = cls._normalize_layer(
                texto.get("capa")
            )

            if not cls._is_dimension_layer(capa):
                continue

            valor_m = cls._parse_dimension_value(
                texto.get("text", "")
            )

            if valor_m is None:
                continue

            tx = float(texto.get("x", 0))
            ty = float(texto.get("y", 0))
            page = texto.get("page")

            candidatos = []

            for linea in lineas_cotas:
                if linea.get("page") != page:
                    continue

                try:
                    x1 = float(linea["x1"])
                    y1 = float(linea["y1"])
                    x2 = float(linea["x2"])
                    y2 = float(linea["y2"])
                except (KeyError, TypeError, ValueError):
                    continue

                distancia = cls._distancia_punto_segmento(
                    tx,
                    ty,
                    x1,
                    y1,
                    x2,
                    y2,
                )

                longitud_pdf = math.hypot(
                    x2 - x1,
                    y2 - y1,
                )

                if longitud_pdf <= 0.001:
                    continue

                candidatos.append(
                    (
                        distancia,
                        longitud_pdf,
                        linea,
                    )
                )

            if not candidatos:
                continue

            candidatos.sort(
                key=lambda item: item[0]
            )

            distancia, longitud_pdf, linea = candidatos[0]

            if distancia > cls.DIMENSION_TEXT_MAX_DISTANCE:
                continue

            factor = valor_m / longitud_pdf

            if not (
                cls.SCALE_FACTOR_MIN
                <= factor
                <= cls.SCALE_FACTOR_MAX
            ):
                continue

            factores.append(factor)

            referencias.append(
                {
                    "valor_m": valor_m,
                    "longitud_pdf": longitud_pdf,
                    "factor": factor,
                    "distancia_texto_linea": distancia,
                    "page": page,
                    "linea_id": linea.get("id"),
                }
            )

        if not factores:
            return {
                "factor_xy": 1.0,
                "source": "default",
                "referencias": [],
                "confianza": "sin_referencias_validas",
            }

        factor_mediana = cls._calcular_mediana(
            factores
        )

        # -----------------------------------------------------
        # Filtrar referencias demasiado alejadas de la mediana.
        # -----------------------------------------------------

        referencias_validas = []

        for referencia in referencias:
            factor = referencia["factor"]

            diferencia_relativa = abs(
                factor - factor_mediana
            ) / factor_mediana

            if diferencia_relativa <= cls.SCALE_OUTLIER_TOLERANCE:
                referencias_validas.append(
                    referencia
                )

        if referencias_validas:
            factores_validos = [
                referencia["factor"]
                for referencia in referencias_validas
            ]

            factor_mediana = cls._calcular_mediana(
                factores_validos
            )

        if len(referencias_validas) >= 2:
            confianza = "alta"
        elif len(referencias_validas) == 1:
            confianza = "media"
        else:
            confianza = "baja"

        return {
            "factor_xy": float(factor_mediana),
            "source": "dimension",
            "referencias": referencias_validas,
            "confianza": confianza,
        }

    # =========================================================
    # CONVERSIÓN DEL MODELO A METROS
    # =========================================================

    @classmethod
    def _convertir_punto_a_metros(
        cls,
        x: float,
        y: float,
        factor_xy: float,
        origen_x: float,
        origen_y: float,
        altura_pagina: float,
    ) -> Dict[str, float]:
        """
        Convierte una coordenada PDF a metros.

        Se elimina el origen PDF y se invierte el eje Y para utilizar
        un sistema cartesiano convencional:

            X → derecha
            Y → arriba

        El origen queda en la esquina inferior izquierda del
        bounding box del plano.
        """

        x_m = (
            float(x) - origen_x
        ) * factor_xy

        y_m = (
            altura_pagina - float(y)
            - origen_y
        ) * factor_xy

        return {
            "x": x_m,
            "y": y_m,
        }

    @classmethod
    def _convertir_linea_a_metros(
        cls,
        linea: Dict[str, Any],
        factor_xy: float,
        origen_x: float,
        origen_y: float,
        altura_pagina: float,
    ) -> Dict[str, Any]:
        """
        Convierte una línea completa a metros.
        """
        p1 = cls._convertir_punto_a_metros(
            linea["x1"],
            linea["y1"],
            factor_xy,
            origen_x,
            origen_y,
            altura_pagina,
        )

        p2 = cls._convertir_punto_a_metros(
            linea["x2"],
            linea["y2"],
            factor_xy,
            origen_x,
            origen_y,
            altura_pagina,
        )

        resultado = dict(linea)

        resultado["x1"] = p1["x"]
        resultado["y1"] = p1["y"]
        resultado["x2"] = p2["x"]
        resultado["y2"] = p2["y"]

        return resultado

    @classmethod
    def _convertir_poligono_a_metros(
        cls,
        poligono: Dict[str, Any],
        factor_xy: float,
        origen_x: float,
        origen_y: float,
        altura_pagina: float,
    ) -> Dict[str, Any]:
        """
        Convierte un polígono completo a metros.
        """
        resultado = dict(poligono)

        puntos = []

        for punto in poligono.get("puntos", []):
            convertido = cls._convertir_punto_a_metros(
                punto["x"],
                punto["y"],
                factor_xy,
                origen_x,
                origen_y,
                altura_pagina,
            )

            puntos.append(convertido)

        resultado["puntos"] = puntos

        if puntos:
            xs = [p["x"] for p in puntos]
            ys = [p["y"] for p in puntos]

            resultado["bounding_box"] = {
                "min_x": min(xs),
                "min_y": min(ys),
                "max_x": max(xs),
                "max_y": max(ys),
            }

            resultado["centro"] = {
                "x": sum(xs) / len(xs),
                "y": sum(ys) / len(ys),
            }

        # El área pasa de PDF-points² a m².
        resultado["area"] = (
            float(poligono.get("area", 0.0))
            * factor_xy
            * factor_xy
        )

        return resultado

    @classmethod
    def _convertir_nivel_a_metros(
        cls,
        nivel: Dict[str, Any],
        factor_xy: float,
        origen_x: float,
        origen_y: float,
        altura_pagina: float,
    ) -> Dict[str, Any]:
        """
        Convierte la posición XY del nivel.

        IMPORTANTE:
        `valor` NO se multiplica por el factor.

        Si el PDF dice +7.90, ese valor ya representa 7.90 m
        de altura arquitectónica.
        """
        resultado = dict(nivel)

        punto = cls._convertir_punto_a_metros(
            nivel.get("x", 0.0),
            nivel.get("y", 0.0),
            factor_xy,
            origen_x,
            origen_y,
            altura_pagina,
        )

        resultado["x"] = punto["x"]
        resultado["y"] = punto["y"]
        resultado["posicion"] = punto

        resultado["valor"] = float(
            nivel.get("valor", 0.0)
        )

        return resultado

    @classmethod
    def _convertir_level_mark_a_metros(
        cls,
        marca: Dict[str, Any],
        factor_xy: float,
        origen_x: float,
        origen_y: float,
        altura_pagina: float,
    ) -> Dict[str, Any]:
        resultado = dict(marca)

        punto = cls._convertir_punto_a_metros(
            marca.get("x", 0.0),
            marca.get("y", 0.0),
            factor_xy,
            origen_x,
            origen_y,
            altura_pagina,
        )

        resultado["x"] = punto["x"]
        resultado["y"] = punto["y"]
        resultado["posicion"] = punto

        return resultado

    @classmethod
    def _convertir_texto_a_metros(
        cls,
        texto: Dict[str, Any],
        factor_xy: float,
        origen_x: float,
        origen_y: float,
        altura_pagina: float,
    ) -> Dict[str, Any]:
        resultado = dict(texto)

        punto = cls._convertir_punto_a_metros(
            texto.get("x", 0.0),
            texto.get("y", 0.0),
            factor_xy,
            origen_x,
            origen_y,
            altura_pagina,
        )

        resultado["x"] = punto["x"]
        resultado["y"] = punto["y"]
        resultado["posicion"] = punto

        return resultado

    @classmethod
    def _convertir_bounding_box_a_metros(
        cls,
        bounding_box: Dict[str, Any],
        factor_xy: float,
        origen_x: float,
        origen_y: float,
        altura_pagina: float,
    ) -> Dict[str, float]:
        if not bounding_box:
            return {}

        puntos = [
            cls._convertir_punto_a_metros(
                bounding_box["min_x"],
                bounding_box["min_y"],
                factor_xy,
                origen_x,
                origen_y,
                altura_pagina,
            ),
            cls._convertir_punto_a_metros(
                bounding_box["max_x"],
                bounding_box["max_y"],
                factor_xy,
                origen_x,
                origen_y,
                altura_pagina,
            ),
        ]

        xs = [p["x"] for p in puntos]
        ys = [p["y"] for p in puntos]

        return {
            "min_x": min(xs),
            "min_y": min(ys),
            "max_x": max(xs),
            "max_y": max(ys),
            "width": max(xs) - min(xs),
            "height": max(ys) - min(ys),
        }

    @classmethod
    def convertir_modelo_a_metros(
        cls,
        modelo: Dict[str, Any],
        paginas: "fitz.Document",
        escala: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Convierte el Modelo2D completo a metros y normaliza el eje Y.

        El método se ejecuta DESPUÉS de construir los polígonos y
        asociar los niveles.

        Parámetros:
            modelo:
                Modelo2D generado en coordenadas PDF.

            paginas:
                Documento PDF utilizado para obtener la altura de cada página.

            escala:
                Resultado de _detectar_factor_escala().

        Retorna:
            Modelo2D con coordenadas XY expresadas en metros.
        """

        if escala is None:
            escala = cls._detectar_factor_escala(
                modelo.get("lineas", []),
                modelo.get("textos", []),
            )

        factor_xy = float(
            escala.get("factor_xy", 1.0)
        )

        if factor_xy <= 0:
            raise ValueError(
                "El factor de escala debe ser mayor que cero."
            )

        lineas = modelo.get("lineas", [])
        bounding_box = modelo.get(
            "bounding_box",
            {},
        )

        if bounding_box:
            origen_x = float(
                bounding_box.get("min_x", 0.0)
            )
            origen_y = float(
                bounding_box.get("min_y", 0.0)
            )
        else:
            origen_x = 0.0
            origen_y = 0.0

        resultado = dict(modelo)

        # -----------------------------------------------------
        # LÍNEAS
        # -----------------------------------------------------

        resultado["lineas"] = [
            cls._convertir_linea_a_metros(
                linea,
                factor_xy,
                origen_x,
                origen_y,
                float(
                    paginas[linea.get("page", 0)].rect.height
                ),
            )
            for linea in lineas
        ]

        # -----------------------------------------------------
        # POLÍGONOS
        # -----------------------------------------------------

        resultado["poligonos"] = [
            cls._convertir_poligono_a_metros(
                poligono,
                factor_xy,
                origen_x,
                origen_y,
                float(
                    paginas[
                        poligono.get("page", 0)
                    ].rect.height
                ),
            )
            for poligono in modelo.get("poligonos", [])
        ]

        # -----------------------------------------------------
        # ROOF LINES
        # -----------------------------------------------------

        resultado["roof_lines"] = [
            cls._convertir_linea_a_metros(
                linea,
                factor_xy,
                origen_x,
                origen_y,
                float(
                    paginas[linea.get("page", 0)].rect.height
                ),
            )
            for linea in modelo.get("roof_lines", [])
        ]

        # -----------------------------------------------------
        # AUX ROOF
        # -----------------------------------------------------

        resultado["aux_roof"] = [
            cls._convertir_linea_a_metros(
                linea,
                factor_xy,
                origen_x,
                origen_y,
                float(
                    paginas[linea.get("page", 0)].rect.height
                ),
            )
            for linea in modelo.get("aux_roof", [])
        ]

        # -----------------------------------------------------
        # NIVELES
        # -----------------------------------------------------

        niveles_convertidos = [
            cls._convertir_nivel_a_metros(
                nivel,
                factor_xy,
                origen_x,
                origen_y,
                float(
                    paginas[nivel.get("page", 0)].rect.height
                ),
            )
            for nivel in modelo.get("niveles", [])
        ]

        resultado["niveles"] = niveles_convertidos

        # cotas_altura es la misma colección lógica de niveles.
        resultado["cotas_altura"] = niveles_convertidos

        # -----------------------------------------------------
        # SÍMBOLOS DE NIVEL
        # -----------------------------------------------------

        resultado["level_marks"] = [
            cls._convertir_level_mark_a_metros(
                marca,
                factor_xy,
                origen_x,
                origen_y,
                float(
                    paginas[marca.get("page", 0)].rect.height
                ),
            )
            for marca in modelo.get("level_marks", [])
        ]

        # -----------------------------------------------------
        # TEXTOS
        # -----------------------------------------------------

        resultado["textos"] = [
            cls._convertir_texto_a_metros(
                texto,
                factor_xy,
                origen_x,
                origen_y,
                float(
                    paginas[texto.get("page", 0)].rect.height
                ),
            )
            for texto in modelo.get("textos", [])
        ]

        # -----------------------------------------------------
        # BOUNDING BOX
        # -----------------------------------------------------

        resultado["bounding_box"] = (
            cls._convertir_bounding_box_a_metros(
                bounding_box,
                factor_xy,
                origen_x,
                origen_y,
                float(paginas[0].rect.height),
            )
            if bounding_box
            else {}
        )

        # -----------------------------------------------------
        # METADATOS DE ESCALA
        # -----------------------------------------------------

        resultado["units"] = "meters"

        resultado["scale"] = {
            "factor_xy": factor_xy,
            "source": escala.get(
                "source",
                "default",
            ),
            "confidence": escala.get(
                "confianza",
                "desconocida",
            ),
            "referencias": escala.get(
                "referencias",
                [],
            ),
            "origen_pdf": {
                "x": origen_x,
                "y": origen_y,
            },
            "conversion": "pdf-points -> meters",
        }

        return resultado

    # =========================================================
    # NIVELES
    # =========================================================

    @classmethod
    def _to_level_value(
        cls,
        sign: Optional[str],
        number: str,
    ) -> Optional[float]:
        try:
            value = float(
                number.replace(",", ".")
            )
        except ValueError:
            return None

        if sign in ("-", "−", "–"):
            value = -value

        if (
            NivelesUtils.NIVEL_MINIMO
            <= value
            <= NivelesUtils.NIVEL_MAXIMO
        ):
            return value

        return None

    @classmethod
    def _parse_level_text(
        cls,
        text: str,
        *,
        en_capa_niveles: bool,
    ) -> Optional[float]:
        """
        Convierte textos como:

            +7.90
            + 7.90
            -1.20
            +6,10
            ±0.00
        """

        clean = (text or "").strip()

        if not clean or len(clean) > 40:
            return None

        match = cls.LEVEL_TEXT_PATTERN.match(
            clean
        )

        if match:
            sign, number = (
                match.group(1),
                match.group(2),
            )

            if (
                sign is None
                and not en_capa_niveles
            ):
                return None

            return cls._to_level_value(
                sign,
                number,
            )

        if en_capa_niveles:
            match = cls.LEVEL_EMBEDDED_PATTERN.search(
                clean
            )

            if match:
                return cls._to_level_value(
                    match.group(1),
                    match.group(2),
                )

        return None

    @classmethod
    def _create_level(
        cls,
        *,
        level_id: str,
        value: float,
        text: str,
        x: float,
        y: float,
        page: int,
        layer: str = "LEVELS",
    ) -> Dict[str, Any]:
        return {
            "id": level_id,
            "valor": float(value),
            "texto": text.strip(),
            "x": float(x),
            "y": float(y),
            "posicion": cls._point_dict(x, y),
            "page": page,
            "capa": layer,
            "origen": "texto",
            "asociaciones": [],
            "asociado": False,
        }

    # =========================================================
    # TEXTOS
    # =========================================================

    @classmethod
    def _indice_capas_texto(
        cls,
        page: "fitz.Page",
    ) -> List[
        Tuple[float, float, float, float, str]
    ]:
        """Obtiene bbox y capa de cada texto."""
        try:
            trazas = page.get_texttrace()
        except Exception:
            return []

        indice = []

        for span in trazas:
            bbox = span.get("bbox")

            if not bbox:
                continue

            indice.append(
                (
                    float(bbox[0]),
                    float(bbox[1]),
                    float(bbox[2]),
                    float(bbox[3]),
                    cls._normalize_layer(
                        span.get("layer")
                    ),
                )
            )

        return indice

    @staticmethod
    def _capa_de_texto(
        bbox: Sequence[float],
        indice,
    ) -> str:
        cx = (
            bbox[0] + bbox[2]
        ) / 2.0

        cy = (
            bbox[1] + bbox[3]
        ) / 2.0

        for (
            x0,
            y0,
            x1,
            y1,
            capa,
        ) in indice:
            if (
                x0 - 0.5 <= cx <= x1 + 0.5
                and
                y0 - 0.5 <= cy <= y1 + 0.5
            ):
                return capa

        return ""

    @classmethod
    def _leer_textos(
        cls,
        page: "fitz.Page",
        page_number: int,
        textos: List[Dict[str, Any]],
        niveles: List[Dict[str, Any]],
        capas_detectadas: set,
    ) -> None:
        """Lee textos y detecta niveles."""
        try:
            contenido = page.get_text("dict")
        except Exception:
            return

        indice_capas = cls._indice_capas_texto(
            page
        )

        for _, _, _, _, capa in indice_capas:
            if capa:
                capas_detectadas.add(capa)

        for block_index, block in enumerate(
            contenido.get("blocks", [])
        ):
            if block.get("type") != 0:
                continue

            lineas_texto: List[str] = []

            for line in block.get(
                "lines",
                [],
            ):
                texto = "".join(
                    span.get("text", "")
                    for span in line.get(
                        "spans",
                        [],
                    )
                ).strip()

                if not texto:
                    continue

                lineas_texto.append(texto)

                bbox = line.get("bbox")

                if (
                    not bbox
                    or not any(
                        c.isdigit()
                        for c in texto
                    )
                ):
                    continue

                capa = cls._capa_de_texto(
                    bbox,
                    indice_capas,
                )

                if (
                    capa
                    and cls._is_dimension_layer(capa)
                ):
                    continue

                valor = cls._parse_level_text(
                    texto,
                    en_capa_niveles=(
                        bool(capa)
                        and cls._is_level_layer(capa)
                    ),
                )

                if valor is None:
                    continue

                x = (
                    bbox[0] + bbox[2]
                ) / 2.0

                y = (
                    bbox[1] + bbox[3]
                ) / 2.0

                if cls._es_duplicado(
                    niveles,
                    valor,
                    x,
                    y,
                    page_number,
                ):
                    continue

                niveles.append(
                    cls._create_level(
                        level_id=(
                            f"p{page_number}"
                            f"-nivel-"
                            f"{len(niveles) + 1:03d}"
                        ),
                        value=valor,
                        text=texto,
                        x=x,
                        y=y,
                        page=page_number,
                        layer=(
                            capa or "LEVELS"
                        ),
                    )
                )

            texto_bloque = "\n".join(
                lineas_texto
            )

            if texto_bloque:
                bx = float(
                    block["bbox"][0]
                )
                by = float(
                    block["bbox"][1]
                )

                textos.append(
                    {
                        "id": (
                            f"p{page_number}"
                            f"-text-"
                            f"{block_index}"
                        ),
                        "text": texto_bloque[:500],
                        "x": bx,
                        "y": by,
                        "posicion": cls._point_dict(
                            bx,
                            by,
                        ),
                        "page": page_number,
                        "capa": capa,
                    }
                )

    @classmethod
    def _es_duplicado(
        cls,
        niveles: List[Dict[str, Any]],
        valor: float,
        x: float,
        y: float,
        page: int,
    ) -> bool:
        for nivel in niveles:
            if (
                nivel["page"] == page
                and abs(
                    nivel["valor"] - valor
                ) < 1e-9
                and math.hypot(
                    nivel["x"] - x,
                    nivel["y"] - y,
                ) < cls.LEVEL_DEDUP_DISTANCE
            ):
                return True

        return False

    # =========================================================
    # DRAWINGS
    # =========================================================

    @classmethod
    def _segmentos_de_item(
        cls,
        item: Tuple,
    ) -> List[
        Tuple[str, Punto, Punto, float]
    ]:
        """Convierte un item PDF en segmentos."""

        tipo = item[0]

        if tipo == "l":
            a, b = item[1], item[2]

            return [
                (
                    "line",
                    (
                        float(a.x),
                        float(a.y),
                    ),
                    (
                        float(b.x),
                        float(b.y),
                    ),
                    0.98,
                )
            ]

        if tipo in ("re", "qu"):
            if tipo == "re":
                r = item[1]

                pts = [
                    (
                        float(r.x0),
                        float(r.y0),
                    ),
                    (
                        float(r.x1),
                        float(r.y0),
                    ),
                    (
                        float(r.x1),
                        float(r.y1),
                    ),
                    (
                        float(r.x0),
                        float(r.y1),
                    ),
                ]
            else:
                q = item[1]

                pts = [
                    (
                        float(q.ul.x),
                        float(q.ul.y),
                    ),
                    (
                        float(q.ur.x),
                        float(q.ur.y),
                    ),
                    (
                        float(q.lr.x),
                        float(q.lr.y),
                    ),
                    (
                        float(q.ll.x),
                        float(q.ll.y),
                    ),
                ]

            prefijo = (
                "rect"
                if tipo == "re"
                else "quad"
            )

            return [
                (
                    f"{prefijo}-{i}",
                    pts[i],
                    pts[(i + 1) % 4],
                    0.96,
                )
                for i in range(4)
            ]

        if tipo == "c":
            p1, p2, p3, p4 = [
                (
                    float(p.x),
                    float(p.y),
                )
                for p in item[1:5]
            ]

            n = cls.CURVE_SEGMENTS
            puntos: List[Punto] = []

            for i in range(n + 1):
                t = i / n
                m = 1.0 - t

                puntos.append(
                    (
                        m**3 * p1[0]
                        + 3 * m * m * t * p2[0]
                        + 3 * m * t * t * p3[0]
                        + t**3 * p4[0],
                        m**3 * p1[1]
                        + 3 * m * m * t * p2[1]
                        + 3 * m * t * t * p3[1]
                        + t**3 * p4[1],
                    )
                )

            return [
                (
                    f"curve-{i}",
                    puntos[i],
                    puntos[i + 1],
                    0.90,
                )
                for i in range(n)
            ]

        return []

    @classmethod
    def _procesar_drawing(
        cls,
        drawing: Dict[str, Any],
        *,
        drawing_id: str,
        page_number: int,
        layer: str,
        lineas: List[Dict[str, Any]],
        roof_segmentos: Dict[
            int,
            List[Segmento],
        ],
        aux_segmentos: List[
            Tuple[int, Segmento]
        ],
        level_marks: List[
            Dict[str, Any]
        ],
    ) -> None:
        """Procesa un drawing completo."""

        es_roof = cls._is_roof_layer(layer)
        es_aux = cls._is_aux_roof_layer(layer)

        if cls._is_level_symbol_layer(
            layer
        ):
            rect = drawing.get("rect")

            if rect is not None:
                x = (
                    float(rect.x0)
                    + float(rect.x1)
                ) / 2.0

                y = (
                    float(rect.y0)
                    + float(rect.y1)
                ) / 2.0

                level_marks.append(
                    {
                        "id": (
                            f"{drawing_id}"
                            f"-level-symbol"
                        ),
                        "x": x,
                        "y": y,
                        "posicion": cls._point_dict(
                            x,
                            y,
                        ),
                        "page": page_number,
                        "capa": layer,
                        "tipo": "simbolo",
                    }
                )

        def registrar(
            sufijo_id: str,
            a: Punto,
            b: Punto,
            confianza: float,
        ):
            lineas.append(
                {
                    "id": (
                        f"{drawing_id}"
                        f"-{sufijo_id}"
                    ),
                    "type": "line",
                    "x1": a[0],
                    "y1": a[1],
                    "x2": b[0],
                    "y2": b[1],
                    "page": page_number,
                    "capa": layer,
                    "confidence": confianza,
                }
            )

            if math.dist(a, b) <= 0.001:
                return

            if es_roof:
                roof_segmentos[
                    page_number
                ].append((a, b))

            elif es_aux:
                aux_segmentos.append(
                    (
                        page_number,
                        (a, b),
                    )
                )

        subpaths: List[
            Tuple[Punto, Punto]
        ] = []

        actual: Optional[
            Tuple[Punto, Punto]
        ] = None

        for item_index, item in enumerate(
            drawing.get("items", [])
        ):
            if not item:
                continue

            tipo = item[0]

            if (
                tipo == "c"
                and not (es_roof or es_aux)
            ):
                continue

            try:
                segmentos = (
                    cls._segmentos_de_item(
                        item
                    )
                )
            except Exception:
                continue

            for (
                sufijo,
                a,
                b,
                confianza,
            ) in segmentos:
                registrar(
                    f"i{item_index}-{sufijo}",
                    a,
                    b,
                    confianza,
                )

            if (
                tipo in ("l", "c")
                and segmentos
            ):
                inicio = segmentos[0][1]
                fin = segmentos[-1][2]

                if (
                    actual
                    and math.dist(
                        actual[1],
                        inicio,
                    ) <= 1e-3
                ):
                    actual = (
                        actual[0],
                        fin,
                    )
                else:
                    if actual:
                        subpaths.append(
                            actual
                        )

                    actual = (
                        inicio,
                        fin,
                    )

        if actual:
            subpaths.append(actual)

        if es_roof or es_aux:
            cerrar = bool(
                drawing.get("closePath")
            ) or (
                es_roof
                and "f" in str(
                    drawing.get("type")
                    or ""
                )
            )

            if cerrar:
                for n, (
                    inicio,
                    fin,
                ) in enumerate(subpaths):
                    if (
                        math.dist(
                            inicio,
                            fin,
                        ) > 1e-6
                    ):
                        registrar(
                            f"close-{n}",
                            fin,
                            inicio,
                            0.90,
                        )

    # =========================================================
    # POLÍGONOS ROOF
    # =========================================================

    @staticmethod
    def _unificar_extremos(
        segmentos: Sequence[Segmento],
        tol: float,
    ) -> List[Segmento]:
        """Junta extremos próximos."""

        celdas: Dict[
            Tuple[int, int],
            List[Punto],
        ] = defaultdict(list)

        def unir(p: Punto) -> Punto:
            cx = int(p[0] // tol)
            cy = int(p[1] // tol)

            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for q in celdas.get(
                        (
                            cx + dx,
                            cy + dy,
                        ),
                        (),
                    ):
                        if (
                            abs(q[0] - p[0])
                            <= tol
                            and
                            abs(q[1] - p[1])
                            <= tol
                        ):
                            return q

            celdas[
                (cx, cy)
            ].append(p)

            return p

        salida = []

        for a, b in segmentos:
            a2 = unir(a)
            b2 = unir(b)

            if a2 != b2:
                salida.append(
                    (a2, b2)
                )

        return salida

    @staticmethod
    def _segmentos_de_geometria(
        geometria,
    ) -> List[Segmento]:
        partes = (
            list(geometria.geoms)
            if hasattr(
                geometria,
                "geoms",
            )
            else [geometria]
        )

        segmentos = []

        for parte in partes:
            coords = list(
                getattr(
                    parte,
                    "coords",
                    [],
                )
            )

            for i in range(
                len(coords) - 1
            ):
                a = (
                    float(coords[i][0]),
                    float(coords[i][1]),
                )

                b = (
                    float(coords[i + 1][0]),
                    float(coords[i + 1][1]),
                )

                if a != b:
                    segmentos.append(
                        (a, b)
                    )

        return segmentos

    @classmethod
    def _cerrar_huecos(
        cls,
        segmentos: Sequence[Segmento],
    ) -> Tuple[
        List[Segmento],
        int,
    ]:
        """Prepara líneas ROOF para polygonize."""

        snap_tol = (
            cls.ROOF_SNAP_TOLERANCE
        )

        gap_tol = (
            cls.ROOF_GAP_TOLERANCE
        )

        segmentos = (
            cls._unificar_extremos(
                segmentos,
                snap_tol,
            )
        )

        if not segmentos:
            return [], 0

        try:
            piezas = (
                cls._segmentos_de_geometria(
                    unary_union(
                        [
                            LineString(s)
                            for s in segmentos
                        ]
                    )
                )
            )
        except Exception:
            return list(segmentos), 0

        def clave(
            p: Punto,
        ) -> Tuple[float, float]:
            return (
                round(p[0], 6),
                round(p[1], 6),
            )

        grado: Counter = Counter()

        for a, b in piezas:
            grado[clave(a)] += 1
            grado[clave(b)] += 1

        celda = max(
            gap_tol * 4.0,
            8.0,
        )

        indice: Dict[
            Tuple[int, int],
            List[int],
        ] = defaultdict(list)

        for i, (a, b) in enumerate(
            piezas
        ):
            for cx in range(
                int(
                    min(a[0], b[0])
                    // celda
                ),
                int(
                    max(a[0], b[0])
                    // celda
                ) + 1,
            ):
                for cy in range(
                    int(
                        min(a[1], b[1])
                        // celda
                    ),
                    int(
                        max(a[1], b[1])
                        // celda
                    ) + 1,
                ):
                    indice[
                        (cx, cy)
                    ].append(i)

        cortes: Dict[
            int,
            List[Punto],
        ] = defaultdict(list)

        conectores = []

        for i, (a, b) in enumerate(
            piezas
        ):
            propios = {
                clave(a),
                clave(b),
            }

            for p in (a, b):
                if (
                    grado[
                        clave(p)
                    ] != 1
                ):
                    continue

                mejor = None
                vistos = {i}

                for cx in range(
                    int(
                        (p[0] - gap_tol)
                        // celda
                    ),
                    int(
                        (p[0] + gap_tol)
                        // celda
                    ) + 1,
                ):
                    for cy in range(
                        int(
                            (p[1] - gap_tol)
                            // celda
                        ),
                        int(
                            (p[1] + gap_tol)
                            // celda
                        ) + 1,
                    ):
                        for j in indice.get(
                            (cx, cy),
                            (),
                        ):
                            if j in vistos:
                                continue

                            vistos.add(j)

                            c, d = piezas[j]

                            if (
                                clave(c)
                                in propios
                                or clave(d)
                                in propios
                            ):
                                continue

                            q, dist = (
                                NivelesUtils
                                .punto_mas_cercano_en_segmento(
                                    p,
                                    c,
                                    d,
                                )
                            )

                            if (
                                dist <= gap_tol
                                and (
                                    mejor is None
                                    or dist < mejor[0]
                                )
                            ):
                                mejor = (
                                    dist,
                                    j,
                                    q,
                                )

                if mejor is None:
                    continue

                _, j, q = mejor
                c, d = piezas[j]

                if (
                    math.dist(q, c)
                    <= snap_tol
                ):
                    q = c

                elif (
                    math.dist(q, d)
                    <= snap_tol
                ):
                    q = d

                else:
                    cortes[j].append(q)

                if (
                    math.dist(p, q)
                    > 1e-9
                ):
                    conectores.append(
                        (p, q)
                    )

        resultado = []

        for j, (a, b) in enumerate(
            piezas
        ):
            if j not in cortes:
                resultado.append(
                    (a, b)
                )
                continue

            cadena = (
                [a]
                + sorted(
                    set(cortes[j]),
                    key=lambda q:
                        math.dist(a, q),
                )
                + [b]
            )

            for k in range(
                len(cadena) - 1
            ):
                if (
                    cadena[k]
                    != cadena[k + 1]
                ):
                    resultado.append(
                        (
                            cadena[k],
                            cadena[k + 1],
                        )
                    )

        resultado.extend(
            conectores
        )

        return (
            resultado,
            len(conectores),
        )

    @classmethod
    def _limpiar_colineales(
        cls,
        puntos: List[Punto],
    ) -> List[Punto]:
        """Elimina vértices colineales."""

        pts = list(puntos)
        i = 0

        while (
            i < len(pts)
            and len(pts) > 3
        ):
            a = pts[i - 1]
            b = pts[i]
            c = pts[
                (i + 1)
                % len(pts)
            ]

            _, d = (
                NivelesUtils
                .punto_mas_cercano_en_segmento(
                    b,
                    a,
                    c,
                )
            )

            if (
                d
                <= cls.ROOF_COLLINEAR_TOLERANCE
            ):
                pts.pop(i)
                i = max(
                    i - 1,
                    0,
                )
            else:
                i += 1

        return pts

    @classmethod
    def _build_roof_polygons(
        cls,
        roof_segmentos: Dict[
            int,
            List[Segmento],
        ],
    ) -> Tuple[
        List[Dict[str, Any]],
        Dict[str, Any],
    ]:
        """Construye polígonos desde ROOF."""

        poligonos = []
        extremos_abiertos = []
        total_abiertos = 0
        total_conectores = 0
        contador = 0

        for page_number in sorted(
            roof_segmentos
        ):
            segmentos = (
                roof_segmentos[
                    page_number
                ]
            )

            if not segmentos:
                continue

            cerrados, conectores = (
                cls._cerrar_huecos(
                    segmentos
                )
            )

            total_conectores += (
                conectores
            )

            try:
                piezas = [
                    LineString(s)
                    for s in cerrados
                ]

                unido = unary_union(
                    piezas
                )

                lista = (
                    list(unido.geoms)
                    if hasattr(
                        unido,
                        "geoms",
                    )
                    else [unido]
                )

                (
                    caras,
                    _cortes,
                    dangles,
                    _invalidos,
                ) = polygonize_full(
                    lista
                )

            except Exception:
                continue

            for dangle in dangles.geoms:
                total_abiertos += 1

                if (
                    len(
                        extremos_abiertos
                    ) < 100
                ):
                    c = list(
                        dangle.coords
                    )

                    extremos_abiertos.append(
                        {
                            "page": page_number,
                            "x1": float(
                                c[0][0]
                            ),
                            "y1": float(
                                c[0][1]
                            ),
                            "x2": float(
                                c[-1][0]
                            ),
                            "y2": float(
                                c[-1][1]
                            ),
                        }
                    )

            ordenadas = sorted(
                (
                    c
                    for c in caras.geoms
                    if not c.is_empty
                ),
                key=lambda c: (
                    round(
                        c.bounds[1],
                        3,
                    ),
                    round(
                        c.bounds[0],
                        3,
                    ),
                ),
            )

            for cara in ordenadas:
                area = float(
                    cara.area
                )

                if (
                    area
                    < cls.ROOF_MIN_AREA
                ):
                    continue

                coords = [
                    (
                        float(x),
                        float(y),
                    )
                    for x, y
                    in cara.exterior.coords[
                        :-1
                    ]
                ]

                coords = (
                    cls._limpiar_colineales(
                        coords
                    )
                )

                if len(coords) < 3:
                    continue

                contador += 1

                minx, miny, maxx, maxy = (
                    cara.bounds
                )

                poligonos.append(
                    {
                        "id": (
                            f"roof_"
                            f"{contador:03d}"
                        ),
                        "tipo": "poligono",
                        "capa": "ROOF",
                        "origen": "pdf",
                        "page": page_number,
                        "puntos": [
                            {
                                "x": x,
                                "y": y,
                            }
                            for x, y in coords
                        ],
                        "area": area,
                        "bounding_box": {
                            "min_x": float(
                                minx
                            ),
                            "min_y": float(
                                miny
                            ),
                            "max_x": float(
                                maxx
                            ),
                            "max_y": float(
                                maxy
                            ),
                        },
                        "centro": {
                            "x": float(
                                cara.centroid.x
                            ),
                            "y": float(
                                cara.centroid.y
                            ),
                        },
                        "niveles": [],
                        "nivel_bajo": None,
                        "nivel_medio": None,
                        "nivel_alto": None,
                        "pendiente": None,
                        "tipo_cubierta": (
                            "pendiente_por_resolver"
                        ),
                    }
                )

        diagnostico = {
            "roof_conectores_agregados": (
                total_conectores
            ),
            "roof_extremos_abiertos": (
                total_abiertos
            ),
            "roof_extremos_abiertos_muestra": (
                extremos_abiertos
            ),
        }

        return (
            poligonos,
            diagnostico,
        )

    # =========================================================
    # BOUNDING BOX
    # =========================================================

    @classmethod
    def _calculate_bounding_box(
        cls,
        lineas: List[Dict[str, Any]],
    ) -> Dict[str, float]:
        if not lineas:
            return {}

        xs = []
        ys = []

        for line in lineas:
            xs.extend(
                [
                    float(line["x1"]),
                    float(line["x2"]),
                ]
            )

            ys.extend(
                [
                    float(line["y1"]),
                    float(line["y2"]),
                ]
            )

        return {
            "min_x": min(xs),
            "min_y": min(ys),
            "max_x": max(xs),
            "max_y": max(ys),
            "width": max(xs) - min(xs),
            "height": max(ys) - min(ys),
        }

    # =========================================================
    # INTERPRETACIÓN PRINCIPAL
    # =========================================================

    @classmethod
    def interpret_pdf_data(
        cls,
        doc: "fitz.Document",
        file_bytes: bytes | None = None,
    ) -> Dict[str, Any]:
        """
        Interpreta todo el PDF.

        IMPORTANTE:
        La asociación de niveles ocurre antes de convertir a metros.
        Esto mantiene intacta la lógica existente de NivelesUtils.
        """

        lineas = []
        roof_segmentos = defaultdict(list)
        aux_segmentos = []
        niveles_detectados = []
        level_marks = []
        textos = []
        capas_detectadas = set()

        # -----------------------------------------------------
        # EXTRACCIÓN
        # -----------------------------------------------------

        for page_number, page in enumerate(doc):
            cls._leer_textos(
                page,
                page_number,
                textos,
                niveles_detectados,
                capas_detectadas,
            )

            # ÚNICO recorrido de drawings.
            for drawing_index, drawing in enumerate(
                page.get_drawings()
            ):
                layer = cls._normalize_layer(
                    drawing.get("layer")
                )

                if layer:
                    capas_detectadas.add(
                        layer
                    )

                cls._procesar_drawing(
                    drawing,
                    drawing_id=(
                        f"p{page_number}"
                        f"-d{drawing_index}"
                    ),
                    page_number=page_number,
                    layer=layer,
                    lineas=lineas,
                    roof_segmentos=(
                        roof_segmentos
                    ),
                    aux_segmentos=(
                        aux_segmentos
                    ),
                    level_marks=(
                        level_marks
                    ),
                )

        # -----------------------------------------------------
        # POLÍGONOS
        # -----------------------------------------------------

        poligonos, diagnostico = (
            cls._build_roof_polygons(
                roof_segmentos
            )
        )

        # -----------------------------------------------------
        # NIVELES -> POLÍGONOS
        #
        # NO TOCAR.
        # -----------------------------------------------------

        niveles, descartados = (
            NivelesUtils
            .asociar_niveles_automaticamente(
                poligonos,
                niveles_detectados,
                cls.NIVEL_DISTANCIA_MAXIMA,
            )
        )

        NivelesUtils.reconstruir_niveles_poligonos(
            poligonos,
            niveles,
        )

        # -----------------------------------------------------
        # SALIDAS AUXILIARES
        # -----------------------------------------------------

        roof_lines = [
            {
                "x1": a[0],
                "y1": a[1],
                "x2": b[0],
                "y2": b[1],
                "page": page,
                "capa": "ROOF",
            }
            for page, segmentos
            in roof_segmentos.items()
            for a, b in segmentos
        ]

        aux_roof = [
            {
                "id": (
                    f"aux_roof_"
                    f"{index:04d}"
                ),
                "tipo": "linea_pendiente",
                "capa": "AUX_ROOF",
                "page": page,
                "x1": a[0],
                "y1": a[1],
                "x2": b[0],
                "y2": b[1],
            }
            for index, (
                page,
                (a, b),
            ) in enumerate(
                aux_segmentos,
                start=1,
            )
        ]

        # -----------------------------------------------------
        # MODELO ANTES DE ESCALA
        # -----------------------------------------------------

        modelo = {
            "version": "0.5.0",
            "units": "pdf-points",
            "coordinate_system": (
                "pdf-native"
            ),
            "pages": len(doc),
            "capas": sorted(
                capas_detectadas
            ),
            "lineas": lineas,
            "roof_lines": roof_lines,
            "aux_roof": aux_roof,
            "poligonos": poligonos,
            "niveles": niveles,
            "cotas_altura": niveles,
            "niveles_descartados": (
                descartados[:500]
            ),
            "level_marks": level_marks,
            "textos": textos[:1000],
            "bounding_box": (
                cls._calculate_bounding_box(
                    lineas
                )
            ),
            "diagnostico": diagnostico,
        }

        # -----------------------------------------------------
        # ESCALA
        # -----------------------------------------------------

        escala = cls._detectar_factor_escala(
            lineas,
            textos,
        )

        # -----------------------------------------------------
        # CONVERSIÓN FINAL
        # -----------------------------------------------------

        modelo = cls.convertir_modelo_a_metros(
            modelo,
            doc,
            escala,
        )

        # -----------------------------------------------------
        # RESUMEN FINAL
        # -----------------------------------------------------

        modelo["resumen"] = {
            "cantidad_lineas": len(
                modelo["lineas"]
            ),
            "cantidad_lineas_roof": len(
                modelo["roof_lines"]
            ),
            "cantidad_lineas_aux_roof": len(
                modelo["aux_roof"]
            ),
            "cantidad_poligonos_roof": len(
                modelo["poligonos"]
            ),
            "cantidad_niveles_detectados": len(
                niveles_detectados
            ),
            "cantidad_niveles": len(
                modelo["niveles"]
            ),
            "cantidad_niveles_descartados": len(
                descartados
            ),
            "cantidad_simbolos_nivel": len(
                modelo["level_marks"]
            ),
            "cantidad_textos": len(
                modelo["textos"]
            ),
            "unidad_geometria": "metros",
            "factor_escala_xy": modelo[
                "scale"
            ]["factor_xy"],
            "origen_coordenadas": (
                "bounding_box"
            ),
        }

        return modelo

    # =========================================================
    # VALIDACIÓN
    # =========================================================

    @classmethod
    def validate_and_read_pdf(
        cls,
        file_bytes: bytes,
        filename: str,
    ) -> "fitz.Document":
        """Valida y abre un PDF."""

        if not file_bytes:
            raise ValueError(
                "El archivo PDF está vacío."
            )

        try:
            doc = fitz.open(
                stream=file_bytes,
                filetype="pdf",
            )
        except Exception as exc:
            raise ValueError(
                f"No se pudo abrir el PDF "
                f"'{filename}': {exc}"
            )

        if doc.page_count == 0:
            doc.close()
            raise ValueError(
                "El PDF no contiene páginas."
            )

        return doc