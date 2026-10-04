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
        detección de niveles (texto + rescate por símbolo)
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

    ROOF_LAYER_PATTERN = re.compile(r"^(?:.*[|$])?ROOF[ _\-]?\d*$")

    AUX_ROOF_LAYER_PATTERN = re.compile(r"^(?:.*[|$])?AUX[ _\-]?ROOF[ _\-]?\d*$")

    LEVEL_LAYER_PATTERN = re.compile(r"^(?:.*[|$])?(?:LEVELS?|NIVELES)[ _\-]?\d*$")

    LEVEL_SYMBOL_LAYER_PATTERN = re.compile(
        r"^(?:.*[|$])?(?:SIMBOL|SYMBOL|SIMBOLO)S?[ _\-]?"
        r"(?:LEVELS?|NIVELES)[ _\-]?\d*$"
    )

    DIMENSION_LAYER_PATTERN = re.compile(
        r"^(?:.*[|$])?(?:COTAS?|DIM|DIMENSIONS?|DIMENSIONES)[ _\-]?\d*$"
    )

    # "+7.90", "+ 7.90", "-1.20", "+6,10", "±0.00", "+7.90 m", "+7.90 m."
    LEVEL_TEXT_PATTERN = re.compile(
        r"^\s*([+\-±−–])?\s*(\d{1,3}(?:[.,]\d{1,3})?)"
        r"\s*(?:m|mts?)?\.?\s*$",
        re.IGNORECASE,
    )

    # "NPT +0.15", "N.T.N. 3.20", "NIVEL: +6.10", "COTA +2.50"
    # Con una palabra de nivel explícita el signo es opcional.
    LEVEL_PREFIX_PATTERN = re.compile(
        r"^\s*(?:N\.?\s?P\.?\s?T|N\.?\s?T\.?\s?N|N\.?\s?F\.?\s?T|"
        r"N\.?\s?N\.?\s?T|NIVEL|NVL|COTA)\.?\s*[:=]?\s*"
        r"([+\-±−–])?\s*(\d{1,3}(?:[.,]\d{1,3})?)"
        r"\s*(?:m|mts?)?\.?\s*$",
        re.IGNORECASE,
    )

    LEVEL_EMBEDDED_PATTERN = re.compile(
        r"(?<![\w.,])([+\-±−–])\s*(\d{1,3}(?:[.,]\d{1,2})?)(?!\d)"
    )

    # Fuera de capas de niveles solo se acepta un signo embebido con
    # exactamente 2 decimales (formato típico de cota de nivel: +7.90).
    LEVEL_EMBEDDED_STRICT_PATTERN = re.compile(
        r"(?<![\w.,])([+\-±−–])\s*(\d{1,3}[.,]\d{2})(?!\d)"
    )

    # Número suelto con 2 decimales: candidato a nivel si hay un símbolo cerca.
    LEVEL_BARE_NUMBER_PATTERN = re.compile(r"^\d{1,3}[.,]\d{2}$")

    SIGN_ONLY_PATTERN = re.compile(r"^[+\-±−–]$")
    STARTS_WITH_NUMBER_PATTERN = re.compile(r"^\d")

    # Normalización de signos Unicode a su equivalente ASCII.
    SIGN_TRANSLATION = str.maketrans(
        {
            "＋": "+",
            "﹢": "+",
            "➕": "+",
            "−": "-",
            "–": "-",
            "—": "-",
            "－": "-",
            "﹣": "-",
        }
    )

    ROOF_SNAP_TOLERANCE = 0.05
    ROOF_GAP_TOLERANCE = 1.5
    ROOF_COLLINEAR_TOLERANCE = 0.02
    ROOF_MIN_AREA = 1.0

    # Espesor mínimo (en puntos PDF) de una cara ROOF. Para una tira de ancho
    # w, 2*area/perimetro ≈ w. Descarta slivers entre líneas paralelas muy
    # juntas (espesor de muro/alero dibujado con dos líneas) que si no se
    # ven como paredes dobles o triples. Ajustar según la escala del plano.
    ROOF_MIN_ESPESOR = 3.0

    # Dos caras con IoU (intersección / unión) mayor a esto se consideran la
    # misma cara dibujada dos veces (capas duplicadas o casi coincidentes).
    ROOF_DUP_IOU = 0.90

    # Cantidad máxima de caras descartadas que se guardan en el diagnóstico.
    ROOF_DESCARTADAS_MAX = 100

    CURVE_SEGMENTS = 12

    NIVEL_DISTANCIA_MAXIMA = NivelesUtils.DISTANCIA_MAXIMA_LADO
    LEVEL_DEDUP_DISTANCE = 2.0

    # ---------------------------------------------------------
    # DETECCIÓN DE NIVELES
    # ---------------------------------------------------------

    # Un texto con signo (+/-/±) dentro de una capa de COTAS se considera
    # nivel (las medidas de cota no llevan signo). Poner False para ignorar
    # TODO texto de capas de cotas.
    ACEPTAR_NIVELES_CON_SIGNO_EN_COTAS = True

    # Un número suelto (sin signo, 2 decimales) fuera de capas de niveles se
    # acepta como nivel si hay un símbolo de nivel a menos de esta distancia
    # (en puntos PDF).
    NIVEL_SIMBOLO_DISTANCIA = 40.0

    # Cantidad máxima de textos rechazados en la capa de niveles que se
    # guardan en el diagnóstico.
    NIVEL_RECHAZADOS_MAX = 50

    # ---------------------------------------------------------
    # ESCALA
    # ---------------------------------------------------------

    # Factor mínimo y máximo razonables: metros / punto PDF.
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
        return re.sub(r"\s+", " ", str(layer).strip().upper())

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
    def _point_dict(x: float, y: float) -> Dict[str, float]:
        return {"x": float(x), "y": float(y)}

    # =========================================================
    # COTAS / ESCALA
    # =========================================================

    @classmethod
    def _parse_dimension_value(cls, text: str) -> Optional[float]:
        """
        Extrae una longitud expresada en metros.

        Ejemplos: 21.60 | 21,60 | 8.50 m | 8,50 mts
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
            if cls._is_dimension_layer(cls._normalize_layer(linea.get("capa")))
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
            return math.hypot(px - x1, py - y1)

        t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))

        cx = x1 + t * dx
        cy = y1 + t * dy

        return math.hypot(px - cx, py - cy)

    @classmethod
    def _calcular_mediana(cls, valores: List[float]) -> float:
        """Calcula la mediana de una lista."""
        ordenados = sorted(valores)

        if not ordenados:
            return 1.0

        mitad = len(ordenados) // 2

        if len(ordenados) % 2:
            return ordenados[mitad]

        return (ordenados[mitad - 1] + ordenados[mitad]) / 2.0

    @classmethod
    def _detectar_factor_escala(
        cls,
        lineas: List[Dict[str, Any]],
        textos: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Detecta el factor de conversión (metros / punto PDF) utilizando
        cotas del plano. Se usan varias cotas cuando están disponibles y se
        toma la mediana para reducir errores de detección.
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
            capa = cls._normalize_layer(texto.get("capa"))

            if not cls._is_dimension_layer(capa):
                continue

            valor_m = cls._parse_dimension_value(texto.get("text", ""))

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

                distancia = cls._distancia_punto_segmento(tx, ty, x1, y1, x2, y2)
                longitud_pdf = math.hypot(x2 - x1, y2 - y1)

                if longitud_pdf <= 0.001:
                    continue

                candidatos.append((distancia, longitud_pdf, linea))

            if not candidatos:
                continue

            candidatos.sort(key=lambda item: item[0])
            distancia, longitud_pdf, linea = candidatos[0]

            if distancia > cls.DIMENSION_TEXT_MAX_DISTANCE:
                continue

            factor = valor_m / longitud_pdf

            if not (cls.SCALE_FACTOR_MIN <= factor <= cls.SCALE_FACTOR_MAX):
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

        factor_mediana = cls._calcular_mediana(factores)

        # Filtrar referencias demasiado alejadas de la mediana.
        referencias_validas = []

        for referencia in referencias:
            diferencia_relativa = (
                abs(referencia["factor"] - factor_mediana) / factor_mediana
            )

            if diferencia_relativa <= cls.SCALE_OUTLIER_TOLERANCE:
                referencias_validas.append(referencia)

        if referencias_validas:
            factor_mediana = cls._calcular_mediana(
                [r["factor"] for r in referencias_validas]
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
        un sistema cartesiano convencional.
        """
        x_m = (float(x) - origen_x) * factor_xy
        y_m = (altura_pagina - float(y) - origen_y) * factor_xy

        return {"x": -x_m, "y": -y_m}

    @classmethod
    def _convertir_linea_a_metros(
        cls,
        linea: Dict[str, Any],
        factor_xy: float,
        origen_x: float,
        origen_y: float,
        altura_pagina: float,
    ) -> Dict[str, Any]:
        """Convierte una línea completa a metros."""
        p1 = cls._convertir_punto_a_metros(
            linea["x1"], linea["y1"], factor_xy, origen_x, origen_y, altura_pagina
        )
        p2 = cls._convertir_punto_a_metros(
            linea["x2"], linea["y2"], factor_xy, origen_x, origen_y, altura_pagina
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
        """Convierte un polígono completo a metros."""
        resultado = dict(poligono)

        puntos = [
            cls._convertir_punto_a_metros(
                punto["x"], punto["y"], factor_xy, origen_x, origen_y, altura_pagina
            )
            for punto in poligono.get("puntos", [])
        ]

        resultado["puntos"] = puntos

        # Huecos (islas interiores): mismo tratamiento que el contorno.
        resultado["huecos"] = [
            [
                cls._convertir_punto_a_metros(
                    punto["x"],
                    punto["y"],
                    factor_xy,
                    origen_x,
                    origen_y,
                    altura_pagina,
                )
                for punto in hueco
            ]
            for hueco in poligono.get("huecos", [])
        ]

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
        resultado["area"] = float(poligono.get("area", 0.0)) * factor_xy * factor_xy

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

        IMPORTANTE: `valor` NO se multiplica por el factor. Si el PDF dice
        +7.90, ese valor ya representa 7.90 m de altura arquitectónica.
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
        resultado["valor"] = float(nivel.get("valor", 0.0))

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

        Se ejecuta DESPUÉS de construir los polígonos y asociar los niveles.
        """
        if escala is None:
            escala = cls._detectar_factor_escala(
                modelo.get("lineas", []),
                modelo.get("textos", []),
            )

        factor_xy = float(escala.get("factor_xy", 1.0))

        if factor_xy <= 0:
            raise ValueError("El factor de escala debe ser mayor que cero.")

        lineas = modelo.get("lineas", [])
        bounding_box = modelo.get("bounding_box", {})

        if bounding_box:
            origen_x = float(bounding_box.get("min_x", 0.0))
            origen_y = float(bounding_box.get("min_y", 0.0))
        else:
            origen_x = 0.0
            origen_y = 0.0

        def altura(item: Dict[str, Any]) -> float:
            return float(paginas[item.get("page", 0)].rect.height)

        resultado = dict(modelo)

        resultado["lineas"] = [
            cls._convertir_linea_a_metros(
                l, factor_xy, origen_x, origen_y, altura(l)
            )
            for l in lineas
        ]

        resultado["poligonos"] = [
            cls._convertir_poligono_a_metros(
                p, factor_xy, origen_x, origen_y, altura(p)
            )
            for p in modelo.get("poligonos", [])
        ]

        resultado["roof_lines"] = [
            cls._convertir_linea_a_metros(
                l, factor_xy, origen_x, origen_y, altura(l)
            )
            for l in modelo.get("roof_lines", [])
        ]

        resultado["aux_roof"] = [
            cls._convertir_linea_a_metros(
                l, factor_xy, origen_x, origen_y, altura(l)
            )
            for l in modelo.get("aux_roof", [])
        ]

        niveles_convertidos = [
            cls._convertir_nivel_a_metros(
                n, factor_xy, origen_x, origen_y, altura(n)
            )
            for n in modelo.get("niveles", [])
        ]

        resultado["niveles"] = niveles_convertidos

        # cotas_altura es la misma colección lógica de niveles.
        resultado["cotas_altura"] = niveles_convertidos

        resultado["level_marks"] = [
            cls._convertir_level_mark_a_metros(
                m, factor_xy, origen_x, origen_y, altura(m)
            )
            for m in modelo.get("level_marks", [])
        ]

        resultado["textos"] = [
            cls._convertir_texto_a_metros(
                t, factor_xy, origen_x, origen_y, altura(t)
            )
            for t in modelo.get("textos", [])
        ]

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

        # Las copias de niveles dentro de cada polígono (x, y, punto_lado,
        # distancia_lado) quedaron en puntos PDF mientras los puntos del
        # polígono ya están en metros. Se regeneran desde cotas_altura
        # (fuente de verdad, ya en metros) para que todo sea coherente.
        if all("asociaciones" in n for n in resultado["niveles"]):
            NivelesUtils.reconstruir_niveles_poligonos(
                resultado["poligonos"], resultado["niveles"]
            )

        resultado["units"] = "meters"

        resultado["scale"] = {
            "factor_xy": factor_xy,
            "source": escala.get("source", "default"),
            "confidence": escala.get("confianza", "desconocida"),
            "referencias": escala.get("referencias", []),
            "origen_pdf": {"x": origen_x, "y": origen_y},
            "conversion": "pdf-points -> meters",
        }

        return resultado

    # =========================================================
    # NIVELES
    # =========================================================

    @classmethod
    def _normalizar_texto_nivel(cls, text: str) -> str:
        """Unifica signos Unicode (＋, −, –, —...) y espacios raros."""
        clean = (text or "").translate(cls.SIGN_TRANSLATION)
        clean = clean.replace("\u00a0", " ").replace("\u2009", " ")
        return clean.strip()

    @classmethod
    def _to_level_value(
        cls,
        sign: Optional[str],
        number: str,
    ) -> Optional[float]:
        try:
            value = float(number.replace(",", "."))
        except ValueError:
            return None

        if sign in ("-", "−", "–"):
            value = -value

        if NivelesUtils.NIVEL_MINIMO <= value <= NivelesUtils.NIVEL_MAXIMO:
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
        Convierte textos de nivel a valor numérico.

        Formatos aceptados:
            +7.90 | + 7.90 | -1.20 | +6,10 | ±0.00 | +7.90 m
            NPT +0.15 | N.T.N. 3.20 | NIVEL: +6.10   (palabra de nivel)
            3.20 / "Cumbrera" ...                    (solo en capa de niveles)
            "+7.90 alero"                            (signo + 2 decimales)
        """
        clean = cls._normalizar_texto_nivel(text)

        if not clean or len(clean) > 40:
            return None

        # 1) Solo número (con signo, o sin signo si está en capa de niveles).
        match = cls.LEVEL_TEXT_PATTERN.match(clean)

        if match:
            sign, number = match.group(1), match.group(2)

            if sign is None and not en_capa_niveles:
                return None

            return cls._to_level_value(sign, number)

        # 2) Con palabra de nivel explícita: el signo es opcional.
        match = cls.LEVEL_PREFIX_PATTERN.match(clean)

        if match:
            return cls._to_level_value(match.group(1), match.group(2))

        # 3) Número embebido en un texto más largo.
        if en_capa_niveles:
            match = cls.LEVEL_EMBEDDED_PATTERN.search(clean)

            if match:
                return cls._to_level_value(match.group(1), match.group(2))

            return None

        # Fuera de capas de niveles: solo si hay UN número en el texto y
        # lleva signo con 2 decimales (evita confundir "1.50 + 2.30").
        if len(re.findall(r"\d+(?:[.,]\d+)?", clean)) == 1:
            match = cls.LEVEL_EMBEDDED_STRICT_PATTERN.search(clean)

            if match:
                return cls._to_level_value(match.group(1), match.group(2))

        return None

    @classmethod
    def _texto_tiene_signo(cls, text: str) -> bool:
        return bool(re.search(r"[+\-±]", cls._normalizar_texto_nivel(text)))

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
        origen: str = "texto",
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
            "origen": origen,
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
    ) -> List[Tuple[float, float, float, float, str, str]]:
        """Obtiene bbox, capa y texto (sin espacios) de cada span."""
        try:
            trazas = page.get_texttrace()
        except Exception:
            return []

        indice = []

        for span in trazas:
            bbox = span.get("bbox")

            if not bbox:
                continue

            try:
                texto_span = "".join(
                    chr(c[0]) for c in span.get("chars", ()) if c
                )
            except Exception:
                texto_span = ""

            indice.append(
                (
                    float(bbox[0]),
                    float(bbox[1]),
                    float(bbox[2]),
                    float(bbox[3]),
                    cls._normalize_layer(span.get("layer")),
                    re.sub(r"\s+", "", texto_span),
                )
            )

        return indice

    @staticmethod
    def _capa_de_texto(
        bbox: Sequence[float],
        indice,
        texto: str = "",
    ) -> str:
        """
        Devuelve la capa del texto. Si varios spans se solapan con el bbox
        (texto de distintas capas superpuesto), se prefiere el que coincide
        con el contenido del texto.
        """
        cx = (bbox[0] + bbox[2]) / 2.0
        cy = (bbox[1] + bbox[3]) / 2.0

        candidatos = [
            (capa, txt)
            for (x0, y0, x1, y1, capa, txt) in indice
            if x0 - 0.5 <= cx <= x1 + 0.5 and y0 - 0.5 <= cy <= y1 + 0.5
        ]

        if not candidatos:
            return ""

        t = re.sub(r"\s+", "", texto or "")

        if t:
            for capa, txt in candidatos:
                if txt and (
                    t == txt or (len(txt) >= 2 and (txt in t or t in txt))
                ):
                    return capa

        return candidatos[0][0]

    @classmethod
    def _fusionar_signos_sueltos(
        cls,
        unidades: List[Tuple[str, Tuple[float, float, float, float]]],
    ) -> List[Tuple[str, Tuple[float, float, float, float]]]:
        """
        Algunos CAD exportan el signo y el número como líneas de texto
        separadas ("+" y "7.90"). Si una línea es solo un signo y la
        siguiente empieza con número, se fusionan en una sola unidad.
        """
        salida = []
        i = 0

        while i < len(unidades):
            texto, bbox = unidades[i]
            limpio = cls._normalizar_texto_nivel(texto)

            if (
                cls.SIGN_ONLY_PATTERN.match(limpio)
                and i + 1 < len(unidades)
                and cls.STARTS_WITH_NUMBER_PATTERN.match(unidades[i + 1][0].strip())
            ):
                texto2, bbox2 = unidades[i + 1]
                fusion_bbox = (
                    min(bbox[0], bbox2[0]),
                    min(bbox[1], bbox2[1]),
                    max(bbox[2], bbox2[2]),
                    max(bbox[3], bbox2[3]),
                )
                salida.append((limpio + texto2.strip(), fusion_bbox))
                i += 2
                continue

            salida.append((texto, bbox))
            i += 1

        return salida

    @classmethod
    def _evaluar_texto_nivel(
        cls,
        texto: str,
        bbox: Sequence[float],
        capa: str,
        page_number: int,
        niveles: List[Dict[str, Any]],
        candidatos_sin_signo: List[Dict[str, Any]],
        rechazados: List[Dict[str, Any]],
    ) -> None:
        """Decide si una línea de texto es un nivel."""
        if not any(c.isdigit() for c in texto):
            return

        es_cotas = bool(capa) and cls._is_dimension_layer(capa)
        en_niveles = bool(capa) and cls._is_level_layer(capa)

        # Las medidas de cota no son niveles; un texto con signo sí puede serlo.
        if es_cotas and not (
            cls.ACEPTAR_NIVELES_CON_SIGNO_EN_COTAS and cls._texto_tiene_signo(texto)
        ):
            return

        x = (bbox[0] + bbox[2]) / 2.0
        y = (bbox[1] + bbox[3]) / 2.0

        valor = cls._parse_level_text(texto, en_capa_niveles=en_niveles)

        if valor is None:
            if en_niveles:
                if len(rechazados) < cls.NIVEL_RECHAZADOS_MAX:
                    rechazados.append(
                        {"texto": texto[:40], "page": page_number, "x": x, "y": y, "capa": capa}
                    )
            elif not es_cotas and cls.LEVEL_BARE_NUMBER_PATTERN.match(texto.strip()):
                # Número suelto: se decide después según símbolos cercanos.
                candidatos_sin_signo.append(
                    {"texto": texto.strip(), "page": page_number, "x": x, "y": y, "capa": capa}
                )
            return

        if cls._es_duplicado(niveles, valor, x, y, page_number):
            return

        niveles.append(
            cls._create_level(
                level_id=f"p{page_number}-nivel-{len(niveles) + 1:03d}",
                value=valor,
                text=texto,
                x=x,
                y=y,
                page=page_number,
                layer=capa or "LEVELS",
            )
        )

    @classmethod
    def _leer_textos(
        cls,
        page: "fitz.Page",
        page_number: int,
        textos: List[Dict[str, Any]],
        niveles: List[Dict[str, Any]],
        capas_detectadas: set,
        candidatos_sin_signo: Optional[List[Dict[str, Any]]] = None,
        rechazados: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Lee textos y detecta niveles."""
        if candidatos_sin_signo is None:
            candidatos_sin_signo = []
        if rechazados is None:
            rechazados = []

        try:
            contenido = page.get_text("dict")
        except Exception:
            return

        indice_capas = cls._indice_capas_texto(page)

        for entrada in indice_capas:
            if entrada[4]:
                capas_detectadas.add(entrada[4])

        for block_index, block in enumerate(contenido.get("blocks", [])):
            if block.get("type") != 0:
                continue

            lineas_texto: List[str] = []
            unidades: List[Tuple[str, Tuple[float, float, float, float]]] = []

            for line in block.get("lines", []):
                texto = "".join(
                    span.get("text", "") for span in line.get("spans", [])
                ).strip()

                if not texto:
                    continue

                lineas_texto.append(texto)

                bbox = line.get("bbox")

                if bbox:
                    unidades.append((texto, tuple(float(v) for v in bbox)))

            # Une signos sueltos ("+" / "7.90") antes de evaluar niveles.
            for texto, bbox in cls._fusionar_signos_sueltos(unidades):
                capa_linea = cls._capa_de_texto(bbox, indice_capas, texto)

                cls._evaluar_texto_nivel(
                    texto,
                    bbox,
                    capa_linea,
                    page_number,
                    niveles,
                    candidatos_sin_signo,
                    rechazados,
                )

            texto_bloque = "\n".join(lineas_texto)

            if texto_bloque:
                bx = float(block["bbox"][0])
                by = float(block["bbox"][1])

                # La capa del bloque se calcula siempre (antes dependía de
                # la última línea con dígitos y podía quedar sin definir).
                capa_bloque = cls._capa_de_texto(
                    block["bbox"], indice_capas, lineas_texto[0]
                )

                textos.append(
                    {
                        "id": f"p{page_number}-text-{block_index}",
                        "text": texto_bloque[:500],
                        "x": bx,
                        "y": by,
                        "posicion": cls._point_dict(bx, by),
                        "page": page_number,
                        "capa": capa_bloque,
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
                and abs(nivel["valor"] - valor) < 1e-9
                and math.hypot(nivel["x"] - x, nivel["y"] - y)
                < cls.LEVEL_DEDUP_DISTANCE
            ):
                return True

        return False

    @classmethod
    def _rescatar_niveles_por_simbolo(
        cls,
        candidatos: List[Dict[str, Any]],
        level_marks: List[Dict[str, Any]],
        niveles: List[Dict[str, Any]],
    ) -> int:
        """
        Un número suelto sin signo (ej. "3.20") fuera de una capa de niveles
        se acepta como nivel positivo si hay un símbolo de nivel cerca.
        Devuelve la cantidad de niveles rescatados.
        """
        if not candidatos or not level_marks:
            return 0

        rescatados = 0

        for cand in candidatos:
            cercano = any(
                m.get("page") == cand["page"]
                and math.hypot(m["x"] - cand["x"], m["y"] - cand["y"])
                <= cls.NIVEL_SIMBOLO_DISTANCIA
                for m in level_marks
            )

            if not cercano:
                continue

            valor = cls._to_level_value(None, cand["texto"])

            if valor is None:
                continue

            if cls._es_duplicado(niveles, valor, cand["x"], cand["y"], cand["page"]):
                continue

            niveles.append(
                cls._create_level(
                    level_id=f"p{cand['page']}-nivel-{len(niveles) + 1:03d}",
                    value=valor,
                    text=cand["texto"],
                    x=cand["x"],
                    y=cand["y"],
                    page=cand["page"],
                    layer=cand.get("capa") or "LEVELS",
                    origen="texto_cerca_de_simbolo",
                )
            )
            rescatados += 1

        return rescatados

    # =========================================================
    # DRAWINGS
    # =========================================================

    @classmethod
    def _segmentos_de_item(
        cls,
        item: Tuple,
    ) -> List[Tuple[str, Punto, Punto, float]]:
        """Convierte un item PDF en segmentos."""
        tipo = item[0]

        if tipo == "l":
            a, b = item[1], item[2]

            return [
                (
                    "line",
                    (float(a.x), float(a.y)),
                    (float(b.x), float(b.y)),
                    0.98,
                )
            ]

        if tipo in ("re", "qu"):
            if tipo == "re":
                r = item[1]
                pts = [
                    (float(r.x0), float(r.y0)),
                    (float(r.x1), float(r.y0)),
                    (float(r.x1), float(r.y1)),
                    (float(r.x0), float(r.y1)),
                ]
            else:
                q = item[1]
                pts = [
                    (float(q.ul.x), float(q.ul.y)),
                    (float(q.ur.x), float(q.ur.y)),
                    (float(q.lr.x), float(q.lr.y)),
                    (float(q.ll.x), float(q.ll.y)),
                ]

            prefijo = "rect" if tipo == "re" else "quad"

            return [
                (f"{prefijo}-{i}", pts[i], pts[(i + 1) % 4], 0.96)
                for i in range(4)
            ]

        if tipo == "c":
            p1, p2, p3, p4 = [(float(p.x), float(p.y)) for p in item[1:5]]

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
                (f"curve-{i}", puntos[i], puntos[i + 1], 0.90)
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
        roof_segmentos: Dict[int, List[Segmento]],
        aux_segmentos: List[Tuple[int, Segmento]],
        level_marks: List[Dict[str, Any]],
    ) -> None:
        """Procesa un drawing completo."""
        es_roof = cls._is_roof_layer(layer)
        es_aux = cls._is_aux_roof_layer(layer)

        if cls._is_level_symbol_layer(layer):
            rect = drawing.get("rect")

            if rect is not None:
                x = (float(rect.x0) + float(rect.x1)) / 2.0
                y = (float(rect.y0) + float(rect.y1)) / 2.0

                level_marks.append(
                    {
                        "id": f"{drawing_id}-level-symbol",
                        "x": x,
                        "y": y,
                        "posicion": cls._point_dict(x, y),
                        "page": page_number,
                        "capa": layer,
                        "tipo": "simbolo",
                    }
                )

        def registrar(sufijo_id: str, a: Punto, b: Punto, confianza: float):
            lineas.append(
                {
                    "id": f"{drawing_id}-{sufijo_id}",
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
                roof_segmentos[page_number].append((a, b))
            elif es_aux:
                aux_segmentos.append((page_number, (a, b)))

        subpaths: List[Tuple[Punto, Punto]] = []
        actual: Optional[Tuple[Punto, Punto]] = None

        for item_index, item in enumerate(drawing.get("items", [])):
            if not item:
                continue

            tipo = item[0]

            if tipo == "c" and not (es_roof or es_aux):
                continue

            try:
                segmentos = cls._segmentos_de_item(item)
            except Exception:
                continue

            for sufijo, a, b, confianza in segmentos:
                registrar(f"i{item_index}-{sufijo}", a, b, confianza)

            if tipo in ("l", "c") and segmentos:
                inicio = segmentos[0][1]
                fin = segmentos[-1][2]

                if actual and math.dist(actual[1], inicio) <= 1e-3:
                    actual = (actual[0], fin)
                else:
                    if actual:
                        subpaths.append(actual)

                    actual = (inicio, fin)

        if actual:
            subpaths.append(actual)

        if es_roof or es_aux:
            cerrar = bool(drawing.get("closePath")) or (
                es_roof and "f" in str(drawing.get("type") or "")
            )

            if cerrar:
                for n, (inicio, fin) in enumerate(subpaths):
                    if math.dist(inicio, fin) > 1e-6:
                        registrar(f"close-{n}", fin, inicio, 0.90)

    # =========================================================
    # POLÍGONOS ROOF
    # =========================================================

    @staticmethod
    def _unificar_extremos(
        segmentos: Sequence[Segmento],
        tol: float,
    ) -> List[Segmento]:
        """Junta extremos próximos."""
        celdas: Dict[Tuple[int, int], List[Punto]] = defaultdict(list)

        def unir(p: Punto) -> Punto:
            cx = int(p[0] // tol)
            cy = int(p[1] // tol)

            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for q in celdas.get((cx + dx, cy + dy), ()):
                        if abs(q[0] - p[0]) <= tol and abs(q[1] - p[1]) <= tol:
                            return q

            celdas[(cx, cy)].append(p)

            return p

        salida = []

        for a, b in segmentos:
            a2 = unir(a)
            b2 = unir(b)

            if a2 != b2:
                salida.append((a2, b2))

        return salida

    @staticmethod
    def _segmentos_de_geometria(geometria) -> List[Segmento]:
        partes = list(geometria.geoms) if hasattr(geometria, "geoms") else [geometria]

        segmentos = []

        for parte in partes:
            coords = list(getattr(parte, "coords", []))

            for i in range(len(coords) - 1):
                a = (float(coords[i][0]), float(coords[i][1]))
                b = (float(coords[i + 1][0]), float(coords[i + 1][1]))

                if a != b:
                    segmentos.append((a, b))

        return segmentos

    @classmethod
    def _cerrar_huecos(
        cls,
        segmentos: Sequence[Segmento],
        snap_tol: Optional[float] = None,
        gap_tol: Optional[float] = None,
    ) -> Tuple[List[Segmento], int]:
        """
        Prepara líneas ROOF para polygonize.

        `snap_tol` y `gap_tol` están en las unidades de las coordenadas de
        entrada. Por defecto usan las constantes de clase (pensadas para
        puntos PDF); un DXF en metros debería pasar valores propios, porque
        1.5 unidades serían 1.5 m y uniría líneas que no deben unirse.
        """
        if snap_tol is None:
            snap_tol = cls.ROOF_SNAP_TOLERANCE

        if gap_tol is None:
            gap_tol = cls.ROOF_GAP_TOLERANCE

        segmentos = cls._unificar_extremos(segmentos, snap_tol)

        if not segmentos:
            return [], 0

        try:
            piezas = cls._segmentos_de_geometria(
                unary_union([LineString(s) for s in segmentos])
            )
        except Exception:
            return list(segmentos), 0

        def clave(p: Punto) -> Tuple[float, float]:
            return (round(p[0], 6), round(p[1], 6))

        grado: Counter = Counter()

        for a, b in piezas:
            grado[clave(a)] += 1
            grado[clave(b)] += 1

        celda = max(gap_tol * 4.0, 8.0)

        indice: Dict[Tuple[int, int], List[int]] = defaultdict(list)

        for i, (a, b) in enumerate(piezas):
            for cx in range(int(min(a[0], b[0]) // celda), int(max(a[0], b[0]) // celda) + 1):
                for cy in range(int(min(a[1], b[1]) // celda), int(max(a[1], b[1]) // celda) + 1):
                    indice[(cx, cy)].append(i)

        cortes: Dict[int, List[Punto]] = defaultdict(list)
        conectores = []

        for i, (a, b) in enumerate(piezas):
            propios = {clave(a), clave(b)}

            for p in (a, b):
                if grado[clave(p)] != 1:
                    continue

                mejor = None
                vistos = {i}

                for cx in range(int((p[0] - gap_tol) // celda), int((p[0] + gap_tol) // celda) + 1):
                    for cy in range(int((p[1] - gap_tol) // celda), int((p[1] + gap_tol) // celda) + 1):
                        for j in indice.get((cx, cy), ()):
                            if j in vistos:
                                continue

                            vistos.add(j)

                            c, d = piezas[j]

                            if clave(c) in propios or clave(d) in propios:
                                continue

                            q, dist = NivelesUtils.punto_mas_cercano_en_segmento(p, c, d)

                            if dist <= gap_tol and (mejor is None or dist < mejor[0]):
                                mejor = (dist, j, q)

                if mejor is None:
                    continue

                _, j, q = mejor
                c, d = piezas[j]

                if math.dist(q, c) <= snap_tol:
                    q = c
                elif math.dist(q, d) <= snap_tol:
                    q = d
                else:
                    cortes[j].append(q)

                if math.dist(p, q) > 1e-9:
                    conectores.append((p, q))

        resultado = []

        for j, (a, b) in enumerate(piezas):
            if j not in cortes:
                resultado.append((a, b))
                continue

            cadena = [a] + sorted(set(cortes[j]), key=lambda q: math.dist(a, q)) + [b]

            for k in range(len(cadena) - 1):
                if cadena[k] != cadena[k + 1]:
                    resultado.append((cadena[k], cadena[k + 1]))

        resultado.extend(conectores)

        return resultado, len(conectores)

    @classmethod
    def _limpiar_colineales(cls, puntos: List[Punto]) -> List[Punto]:
        """Elimina vértices colineales."""
        pts = list(puntos)
        i = 0

        while i < len(pts) and len(pts) > 3:
            a = pts[i - 1]
            b = pts[i]
            c = pts[(i + 1) % len(pts)]

            _, d = NivelesUtils.punto_mas_cercano_en_segmento(b, a, c)

            if d <= cls.ROOF_COLLINEAR_TOLERANCE:
                pts.pop(i)
                i = max(i - 1, 0)
            else:
                i += 1

        return pts

    @classmethod
    def _filtrar_caras(
        cls,
        caras: Sequence[Any],
        descartadas: List[Dict[str, Any]],
        page_number: int,
    ) -> List[Any]:
        """
        Filtra las caras de polygonize para evitar paredes dobles o triples:

        1. Descarta slivers (caras demasiado finas, espesor < ROOF_MIN_ESPESOR).
        2. Descarta duplicados (caras que se solapan casi por completo con
           una cara más grande ya aceptada).

        Cada cara descartada se registra en `descartadas` para diagnóstico.
        """
        validas = []

        for cara in caras:
            if cara.is_empty or cara.area < cls.ROOF_MIN_AREA:
                continue

            perimetro = float(cara.length)
            espesor = 2.0 * float(cara.area) / perimetro if perimetro > 0 else 0.0

            if espesor < cls.ROOF_MIN_ESPESOR:
                if len(descartadas) < cls.ROOF_DESCARTADAS_MAX:
                    descartadas.append(
                        {
                            "motivo": "sliver",
                            "page": page_number,
                            "area": round(float(cara.area), 3),
                            "espesor": round(espesor, 3),
                            "centro": [
                                round(float(cara.centroid.x), 2),
                                round(float(cara.centroid.y), 2),
                            ],
                        }
                    )
                continue

            validas.append(cara)

        unicas: List[Any] = []

        # De mayor a menor: ante un duplicado se conserva la cara más grande.
        for cara in sorted(validas, key=lambda c: -c.area):
            duplicada = False

            for aceptada in unicas:
                try:
                    union = cara.union(aceptada).area

                    if (
                        union > 0
                        and cara.intersection(aceptada).area / union
                        > cls.ROOF_DUP_IOU
                    ):
                        duplicada = True
                        break
                except Exception:
                    continue

            if duplicada:
                if len(descartadas) < cls.ROOF_DESCARTADAS_MAX:
                    descartadas.append(
                        {
                            "motivo": "duplicado",
                            "page": page_number,
                            "area": round(float(cara.area), 3),
                            "centro": [
                                round(float(cara.centroid.x), 2),
                                round(float(cara.centroid.y), 2),
                            ],
                        }
                    )
                continue

            unicas.append(cara)

        return unicas

    @classmethod
    def _build_roof_polygons(
        cls,
        roof_segmentos: Dict[int, List[Segmento]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Construye polígonos desde ROOF."""
        poligonos = []
        caras_descartadas: List[Dict[str, Any]] = []
        total_descartadas = 0
        extremos_abiertos = []
        total_abiertos = 0
        total_conectores = 0
        contador = 0

        for page_number in sorted(roof_segmentos):
            segmentos = roof_segmentos[page_number]

            if not segmentos:
                continue

            cerrados, conectores = cls._cerrar_huecos(segmentos)
            total_conectores += conectores

            try:
                piezas = [LineString(s) for s in cerrados]
                unido = unary_union(piezas)
                lista = list(unido.geoms) if hasattr(unido, "geoms") else [unido]
                caras, _cortes, dangles, _invalidos = polygonize_full(lista)
            except Exception:
                continue

            for dangle in dangles.geoms:
                total_abiertos += 1

                if len(extremos_abiertos) < 100:
                    c = list(dangle.coords)

                    extremos_abiertos.append(
                        {
                            "page": page_number,
                            "x1": float(c[0][0]),
                            "y1": float(c[0][1]),
                            "x2": float(c[-1][0]),
                            "y2": float(c[-1][1]),
                        }
                    )

            antes = len(caras_descartadas)

            caras_ok = cls._filtrar_caras(
                [c for c in caras.geoms if not c.is_empty],
                caras_descartadas,
                page_number,
            )

            total_descartadas += len(caras_descartadas) - antes

            ordenadas = sorted(
                caras_ok,
                key=lambda c: (round(c.bounds[1], 3), round(c.bounds[0], 3)),
            )

            for cara in ordenadas:
                area = float(cara.area)

                if area < cls.ROOF_MIN_AREA:
                    continue

                coords = [
                    (float(x), float(y)) for x, y in cara.exterior.coords[:-1]
                ]

                coords = cls._limpiar_colineales(coords)

                if len(coords) < 3:
                    continue

                # Huecos: islas interiores. Sin esto el contorno exterior
                # cubre también la zona de la isla y esa zona queda cubierta
                # 2 o 3 veces (la isla es además un polígono propio).
                huecos = []

                for anillo in cara.interiors:
                    pts_hueco = cls._limpiar_colineales(
                        [(float(x), float(y)) for x, y in anillo.coords[:-1]]
                    )

                    if len(pts_hueco) >= 3:
                        huecos.append(
                            [{"x": x, "y": y} for x, y in pts_hueco]
                        )

                contador += 1

                minx, miny, maxx, maxy = cara.bounds

                poligonos.append(
                    {
                        "id": f"roof_{contador:03d}",
                        "tipo": "poligono",
                        "capa": "ROOF",
                        "origen": "pdf",
                        "page": page_number,
                        "puntos": [{"x": x, "y": y} for x, y in coords],
                        "huecos": huecos,
                        "area": area,
                        "bounding_box": {
                            "min_x": float(minx),
                            "min_y": float(miny),
                            "max_x": float(maxx),
                            "max_y": float(maxy),
                        },
                        "centro": {
                            "x": float(cara.centroid.x),
                            "y": float(cara.centroid.y),
                        },
                        "niveles": [],
                        "nivel_bajo": None,
                        "nivel_medio": None,
                        "nivel_alto": None,
                        "pendiente": None,
                        "tipo_cubierta": "pendiente_por_resolver",
                    }
                )

        diagnostico = {
            "roof_conectores_agregados": total_conectores,
            "roof_extremos_abiertos": total_abiertos,
            "roof_extremos_abiertos_muestra": extremos_abiertos,
            "roof_caras_descartadas": total_descartadas,
            "roof_caras_descartadas_muestra": caras_descartadas,
        }

        return poligonos, diagnostico

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
            xs.extend([float(line["x1"]), float(line["x2"])])
            ys.extend([float(line["y1"]), float(line["y2"])])

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

        IMPORTANTE: la asociación de niveles ocurre antes de convertir a
        metros. Esto mantiene intacta la lógica existente de NivelesUtils.
        """
        lineas = []
        roof_segmentos = defaultdict(list)
        aux_segmentos = []
        niveles_detectados = []
        level_marks = []
        textos = []
        capas_detectadas = set()
        candidatos_sin_signo: List[Dict[str, Any]] = []
        niveles_rechazados: List[Dict[str, Any]] = []

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
                candidatos_sin_signo,
                niveles_rechazados,
            )

            # ÚNICO recorrido de drawings.
            for drawing_index, drawing in enumerate(page.get_drawings()):
                layer = cls._normalize_layer(drawing.get("layer"))

                if layer:
                    capas_detectadas.add(layer)

                cls._procesar_drawing(
                    drawing,
                    drawing_id=f"p{page_number}-d{drawing_index}",
                    page_number=page_number,
                    layer=layer,
                    lineas=lineas,
                    roof_segmentos=roof_segmentos,
                    aux_segmentos=aux_segmentos,
                    level_marks=level_marks,
                )

        # -----------------------------------------------------
        # RESCATE DE NIVELES SIN SIGNO CERCA DE SÍMBOLOS
        # -----------------------------------------------------

        rescatados = cls._rescatar_niveles_por_simbolo(
            candidatos_sin_signo,
            level_marks,
            niveles_detectados,
        )

        # -----------------------------------------------------
        # POLÍGONOS
        # -----------------------------------------------------

        poligonos, diagnostico = cls._build_roof_polygons(roof_segmentos)

        diagnostico["niveles_rescatados_por_simbolo"] = rescatados
        diagnostico["niveles_rechazados_en_capa_niveles"] = niveles_rechazados

        # -----------------------------------------------------
        # NIVELES -> POLÍGONOS
        #
        # NO TOCAR.
        # -----------------------------------------------------

        niveles, descartados = NivelesUtils.asociar_niveles_automaticamente(
            poligonos,
            niveles_detectados,
            cls.NIVEL_DISTANCIA_MAXIMA,
        )

        NivelesUtils.reconstruir_niveles_poligonos(poligonos, niveles)

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
            for page, segmentos in roof_segmentos.items()
            for a, b in segmentos
        ]

        aux_roof = [
            {
                "id": f"aux_roof_{index:04d}",
                "tipo": "linea_pendiente",
                "capa": "AUX_ROOF",
                "page": page,
                "x1": a[0],
                "y1": a[1],
                "x2": b[0],
                "y2": b[1],
            }
            for index, (page, (a, b)) in enumerate(aux_segmentos, start=1)
        ]

        # -----------------------------------------------------
        # MODELO ANTES DE ESCALA
        # -----------------------------------------------------

        modelo = {
            "version": "0.5.0",
            "units": "pdf-points",
            "coordinate_system": "pdf-native",
            "pages": len(doc),
            "capas": sorted(capas_detectadas),
            "lineas": lineas,
            "roof_lines": roof_lines,
            "aux_roof": aux_roof,
            "poligonos": poligonos,
            "niveles": niveles,
            "cotas_altura": niveles,
            "niveles_descartados": descartados[:500],
            "level_marks": level_marks,
            "textos": textos[:1000],
            "bounding_box": cls._calculate_bounding_box(lineas),
            "diagnostico": diagnostico,
        }

        # -----------------------------------------------------
        # ESCALA
        # -----------------------------------------------------

        escala = cls._detectar_factor_escala(lineas, textos)

        # -----------------------------------------------------
        # CONVERSIÓN FINAL
        # -----------------------------------------------------

        modelo = cls.convertir_modelo_a_metros(modelo, doc, escala)

        # -----------------------------------------------------
        # RESUMEN FINAL
        # -----------------------------------------------------

        modelo["resumen"] = {
            "cantidad_lineas": len(modelo["lineas"]),
            "cantidad_lineas_roof": len(modelo["roof_lines"]),
            "cantidad_lineas_aux_roof": len(modelo["aux_roof"]),
            "cantidad_poligonos_roof": len(modelo["poligonos"]),
            "cantidad_niveles_detectados": len(niveles_detectados),
            "cantidad_niveles_rescatados_por_simbolo": rescatados,
            "cantidad_niveles": len(modelo["niveles"]),
            "cantidad_niveles_descartados": len(descartados),
            "cantidad_simbolos_nivel": len(modelo["level_marks"]),
            "cantidad_textos": len(modelo["textos"]),
            "unidad_geometria": "metros",
            "factor_escala_xy": modelo["scale"]["factor_xy"],
            "origen_coordenadas": "bounding_box",
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
            raise ValueError("El archivo PDF está vacío.")

        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception as exc:
            raise ValueError(f"No se pudo abrir el PDF '{filename}': {exc}")

        if doc.page_count == 0:
            doc.close()
            raise ValueError("El PDF no contiene páginas.")

        return doc
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
        detección de niveles (texto + rescate por símbolo)
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

    ROOF_LAYER_PATTERN = re.compile(r"^(?:.*[|$])?ROOF[ _\-]?\d*$")

    AUX_ROOF_LAYER_PATTERN = re.compile(r"^(?:.*[|$])?AUX[ _\-]?ROOF[ _\-]?\d*$")

    LEVEL_LAYER_PATTERN = re.compile(r"^(?:.*[|$])?(?:LEVELS?|NIVELES)[ _\-]?\d*$")

    LEVEL_SYMBOL_LAYER_PATTERN = re.compile(
        r"^(?:.*[|$])?(?:SIMBOL|SYMBOL|SIMBOLO)S?[ _\-]?"
        r"(?:LEVELS?|NIVELES)[ _\-]?\d*$"
    )

    DIMENSION_LAYER_PATTERN = re.compile(
        r"^(?:.*[|$])?(?:COTAS?|DIM|DIMENSIONS?|DIMENSIONES)[ _\-]?\d*$"
    )

    # "+7.90", "+ 7.90", "-1.20", "+6,10", "±0.00", "+7.90 m", "+7.90 m."
    LEVEL_TEXT_PATTERN = re.compile(
        r"^\s*([+\-±−–])?\s*(\d{1,3}(?:[.,]\d{1,3})?)"
        r"\s*(?:m|mts?)?\.?\s*$",
        re.IGNORECASE,
    )

    # "NPT +0.15", "N.T.N. 3.20", "NIVEL: +6.10", "COTA +2.50"
    # Con una palabra de nivel explícita el signo es opcional.
    LEVEL_PREFIX_PATTERN = re.compile(
        r"^\s*(?:N\.?\s?P\.?\s?T|N\.?\s?T\.?\s?N|N\.?\s?F\.?\s?T|"
        r"N\.?\s?N\.?\s?T|NIVEL|NVL|COTA)\.?\s*[:=]?\s*"
        r"([+\-±−–])?\s*(\d{1,3}(?:[.,]\d{1,3})?)"
        r"\s*(?:m|mts?)?\.?\s*$",
        re.IGNORECASE,
    )

    LEVEL_EMBEDDED_PATTERN = re.compile(
        r"(?<![\w.,])([+\-±−–])\s*(\d{1,3}(?:[.,]\d{1,2})?)(?!\d)"
    )

    # Fuera de capas de niveles solo se acepta un signo embebido con
    # exactamente 2 decimales (formato típico de cota de nivel: +7.90).
    LEVEL_EMBEDDED_STRICT_PATTERN = re.compile(
        r"(?<![\w.,])([+\-±−–])\s*(\d{1,3}[.,]\d{2})(?!\d)"
    )

    # Número suelto con 2 decimales: candidato a nivel si hay un símbolo cerca.
    LEVEL_BARE_NUMBER_PATTERN = re.compile(r"^\d{1,3}[.,]\d{2}$")

    SIGN_ONLY_PATTERN = re.compile(r"^[+\-±−–]$")
    STARTS_WITH_NUMBER_PATTERN = re.compile(r"^\d")

    # Normalización de signos Unicode a su equivalente ASCII.
    SIGN_TRANSLATION = str.maketrans(
        {
            "＋": "+",
            "﹢": "+",
            "➕": "+",
            "−": "-",
            "–": "-",
            "—": "-",
            "－": "-",
            "﹣": "-",
        }
    )

    ROOF_SNAP_TOLERANCE = 0.05
    ROOF_GAP_TOLERANCE = 1.5
    ROOF_COLLINEAR_TOLERANCE = 0.02
    ROOF_MIN_AREA = 1.0
    CURVE_SEGMENTS = 12

    NIVEL_DISTANCIA_MAXIMA = NivelesUtils.DISTANCIA_MAXIMA_LADO
    LEVEL_DEDUP_DISTANCE = 2.0

    # ---------------------------------------------------------
    # DETECCIÓN DE NIVELES
    # ---------------------------------------------------------

    # Un texto con signo (+/-/±) dentro de una capa de COTAS se considera
    # nivel (las medidas de cota no llevan signo). Poner False para ignorar
    # TODO texto de capas de cotas.
    ACEPTAR_NIVELES_CON_SIGNO_EN_COTAS = True

    # Un número suelto (sin signo, 2 decimales) fuera de capas de niveles se
    # acepta como nivel si hay un símbolo de nivel a menos de esta distancia
    # (en puntos PDF).
    NIVEL_SIMBOLO_DISTANCIA = 40.0

    # Cantidad máxima de textos rechazados en la capa de niveles que se
    # guardan en el diagnóstico.
    NIVEL_RECHAZADOS_MAX = 50

    # ---------------------------------------------------------
    # ESCALA
    # ---------------------------------------------------------

    # Factor mínimo y máximo razonables: metros / punto PDF.
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
        return re.sub(r"\s+", " ", str(layer).strip().upper())

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
    def _point_dict(x: float, y: float) -> Dict[str, float]:
        return {"x": float(x), "y": float(y)}

    # =========================================================
    # COTAS / ESCALA
    # =========================================================

    @classmethod
    def _parse_dimension_value(cls, text: str) -> Optional[float]:
        """
        Extrae una longitud expresada en metros.

        Ejemplos: 21.60 | 21,60 | 8.50 m | 8,50 mts
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
            if cls._is_dimension_layer(cls._normalize_layer(linea.get("capa")))
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
            return math.hypot(px - x1, py - y1)

        t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))

        cx = x1 + t * dx
        cy = y1 + t * dy

        return math.hypot(px - cx, py - cy)

    @classmethod
    def _calcular_mediana(cls, valores: List[float]) -> float:
        """Calcula la mediana de una lista."""
        ordenados = sorted(valores)

        if not ordenados:
            return 1.0

        mitad = len(ordenados) // 2

        if len(ordenados) % 2:
            return ordenados[mitad]

        return (ordenados[mitad - 1] + ordenados[mitad]) / 2.0

    @classmethod
    def _detectar_factor_escala(
        cls,
        lineas: List[Dict[str, Any]],
        textos: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Detecta el factor de conversión (metros / punto PDF) utilizando
        cotas del plano. Se usan varias cotas cuando están disponibles y se
        toma la mediana para reducir errores de detección.
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
            capa = cls._normalize_layer(texto.get("capa"))

            if not cls._is_dimension_layer(capa):
                continue

            valor_m = cls._parse_dimension_value(texto.get("text", ""))

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

                distancia = cls._distancia_punto_segmento(tx, ty, x1, y1, x2, y2)
                longitud_pdf = math.hypot(x2 - x1, y2 - y1)

                if longitud_pdf <= 0.001:
                    continue

                candidatos.append((distancia, longitud_pdf, linea))

            if not candidatos:
                continue

            candidatos.sort(key=lambda item: item[0])
            distancia, longitud_pdf, linea = candidatos[0]

            if distancia > cls.DIMENSION_TEXT_MAX_DISTANCE:
                continue

            factor = valor_m / longitud_pdf

            if not (cls.SCALE_FACTOR_MIN <= factor <= cls.SCALE_FACTOR_MAX):
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

        factor_mediana = cls._calcular_mediana(factores)

        # Filtrar referencias demasiado alejadas de la mediana.
        referencias_validas = []

        for referencia in referencias:
            diferencia_relativa = (
                abs(referencia["factor"] - factor_mediana) / factor_mediana
            )

            if diferencia_relativa <= cls.SCALE_OUTLIER_TOLERANCE:
                referencias_validas.append(referencia)

        if referencias_validas:
            factor_mediana = cls._calcular_mediana(
                [r["factor"] for r in referencias_validas]
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
        un sistema cartesiano convencional.
        """
        x_m = (float(x) - origen_x) * factor_xy
        y_m = (altura_pagina - float(y) - origen_y) * factor_xy

        return {"x": -x_m, "y": -y_m}

    @classmethod
    def _convertir_linea_a_metros(
        cls,
        linea: Dict[str, Any],
        factor_xy: float,
        origen_x: float,
        origen_y: float,
        altura_pagina: float,
    ) -> Dict[str, Any]:
        """Convierte una línea completa a metros."""
        p1 = cls._convertir_punto_a_metros(
            linea["x1"], linea["y1"], factor_xy, origen_x, origen_y, altura_pagina
        )
        p2 = cls._convertir_punto_a_metros(
            linea["x2"], linea["y2"], factor_xy, origen_x, origen_y, altura_pagina
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
        """Convierte un polígono completo a metros."""
        resultado = dict(poligono)

        puntos = [
            cls._convertir_punto_a_metros(
                punto["x"], punto["y"], factor_xy, origen_x, origen_y, altura_pagina
            )
            for punto in poligono.get("puntos", [])
        ]

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
        resultado["area"] = float(poligono.get("area", 0.0)) * factor_xy * factor_xy

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

        IMPORTANTE: `valor` NO se multiplica por el factor. Si el PDF dice
        +7.90, ese valor ya representa 7.90 m de altura arquitectónica.
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
        resultado["valor"] = float(nivel.get("valor", 0.0))

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

        Se ejecuta DESPUÉS de construir los polígonos y asociar los niveles.
        """
        if escala is None:
            escala = cls._detectar_factor_escala(
                modelo.get("lineas", []),
                modelo.get("textos", []),
            )

        factor_xy = float(escala.get("factor_xy", 1.0))

        if factor_xy <= 0:
            raise ValueError("El factor de escala debe ser mayor que cero.")

        lineas = modelo.get("lineas", [])
        bounding_box = modelo.get("bounding_box", {})

        if bounding_box:
            origen_x = float(bounding_box.get("min_x", 0.0))
            origen_y = float(bounding_box.get("min_y", 0.0))
        else:
            origen_x = 0.0
            origen_y = 0.0

        def altura(item: Dict[str, Any]) -> float:
            return float(paginas[item.get("page", 0)].rect.height)

        resultado = dict(modelo)

        resultado["lineas"] = [
            cls._convertir_linea_a_metros(
                l, factor_xy, origen_x, origen_y, altura(l)
            )
            for l in lineas
        ]

        resultado["poligonos"] = [
            cls._convertir_poligono_a_metros(
                p, factor_xy, origen_x, origen_y, altura(p)
            )
            for p in modelo.get("poligonos", [])
        ]

        resultado["roof_lines"] = [
            cls._convertir_linea_a_metros(
                l, factor_xy, origen_x, origen_y, altura(l)
            )
            for l in modelo.get("roof_lines", [])
        ]

        resultado["aux_roof"] = [
            cls._convertir_linea_a_metros(
                l, factor_xy, origen_x, origen_y, altura(l)
            )
            for l in modelo.get("aux_roof", [])
        ]

        niveles_convertidos = [
            cls._convertir_nivel_a_metros(
                n, factor_xy, origen_x, origen_y, altura(n)
            )
            for n in modelo.get("niveles", [])
        ]

        resultado["niveles"] = niveles_convertidos

        # cotas_altura es la misma colección lógica de niveles.
        resultado["cotas_altura"] = niveles_convertidos

        resultado["level_marks"] = [
            cls._convertir_level_mark_a_metros(
                m, factor_xy, origen_x, origen_y, altura(m)
            )
            for m in modelo.get("level_marks", [])
        ]

        resultado["textos"] = [
            cls._convertir_texto_a_metros(
                t, factor_xy, origen_x, origen_y, altura(t)
            )
            for t in modelo.get("textos", [])
        ]

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

        # Las copias de niveles dentro de cada polígono (x, y, punto_lado,
        # distancia_lado) quedaron en puntos PDF mientras los puntos del
        # polígono ya están en metros. Se regeneran desde cotas_altura
        # (fuente de verdad, ya en metros) para que todo sea coherente.
        if all("asociaciones" in n for n in resultado["niveles"]):
            NivelesUtils.reconstruir_niveles_poligonos(
                resultado["poligonos"], resultado["niveles"]
            )

        resultado["units"] = "meters"

        resultado["scale"] = {
            "factor_xy": factor_xy,
            "source": escala.get("source", "default"),
            "confidence": escala.get("confianza", "desconocida"),
            "referencias": escala.get("referencias", []),
            "origen_pdf": {"x": origen_x, "y": origen_y},
            "conversion": "pdf-points -> meters",
        }

        return resultado

    # =========================================================
    # NIVELES
    # =========================================================

    @classmethod
    def _normalizar_texto_nivel(cls, text: str) -> str:
        """Unifica signos Unicode (＋, −, –, —...) y espacios raros."""
        clean = (text or "").translate(cls.SIGN_TRANSLATION)
        clean = clean.replace("\u00a0", " ").replace("\u2009", " ")
        return clean.strip()

    @classmethod
    def _to_level_value(
        cls,
        sign: Optional[str],
        number: str,
    ) -> Optional[float]:
        try:
            value = float(number.replace(",", "."))
        except ValueError:
            return None

        if sign in ("-", "−", "–"):
            value = -value

        if NivelesUtils.NIVEL_MINIMO <= value <= NivelesUtils.NIVEL_MAXIMO:
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
        Convierte textos de nivel a valor numérico.

        Formatos aceptados:
            +7.90 | + 7.90 | -1.20 | +6,10 | ±0.00 | +7.90 m
            NPT +0.15 | N.T.N. 3.20 | NIVEL: +6.10   (palabra de nivel)
            3.20 / "Cumbrera" ...                    (solo en capa de niveles)
            "+7.90 alero"                            (signo + 2 decimales)
        """
        clean = cls._normalizar_texto_nivel(text)

        if not clean or len(clean) > 40:
            return None

        # 1) Solo número (con signo, o sin signo si está en capa de niveles).
        match = cls.LEVEL_TEXT_PATTERN.match(clean)

        if match:
            sign, number = match.group(1), match.group(2)

            if sign is None and not en_capa_niveles:
                return None

            return cls._to_level_value(sign, number)

        # 2) Con palabra de nivel explícita: el signo es opcional.
        match = cls.LEVEL_PREFIX_PATTERN.match(clean)

        if match:
            return cls._to_level_value(match.group(1), match.group(2))

        # 3) Número embebido en un texto más largo.
        if en_capa_niveles:
            match = cls.LEVEL_EMBEDDED_PATTERN.search(clean)

            if match:
                return cls._to_level_value(match.group(1), match.group(2))

            return None

        # Fuera de capas de niveles: solo si hay UN número en el texto y
        # lleva signo con 2 decimales (evita confundir "1.50 + 2.30").
        if len(re.findall(r"\d+(?:[.,]\d+)?", clean)) == 1:
            match = cls.LEVEL_EMBEDDED_STRICT_PATTERN.search(clean)

            if match:
                return cls._to_level_value(match.group(1), match.group(2))

        return None

    @classmethod
    def _texto_tiene_signo(cls, text: str) -> bool:
        return bool(re.search(r"[+\-±]", cls._normalizar_texto_nivel(text)))

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
        origen: str = "texto",
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
            "origen": origen,
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
    ) -> List[Tuple[float, float, float, float, str, str]]:
        """Obtiene bbox, capa y texto (sin espacios) de cada span."""
        try:
            trazas = page.get_texttrace()
        except Exception:
            return []

        indice = []

        for span in trazas:
            bbox = span.get("bbox")

            if not bbox:
                continue

            try:
                texto_span = "".join(
                    chr(c[0]) for c in span.get("chars", ()) if c
                )
            except Exception:
                texto_span = ""

            indice.append(
                (
                    float(bbox[0]),
                    float(bbox[1]),
                    float(bbox[2]),
                    float(bbox[3]),
                    cls._normalize_layer(span.get("layer")),
                    re.sub(r"\s+", "", texto_span),
                )
            )

        return indice

    @staticmethod
    def _capa_de_texto(
        bbox: Sequence[float],
        indice,
        texto: str = "",
    ) -> str:
        """
        Devuelve la capa del texto. Si varios spans se solapan con el bbox
        (texto de distintas capas superpuesto), se prefiere el que coincide
        con el contenido del texto.
        """
        cx = (bbox[0] + bbox[2]) / 2.0
        cy = (bbox[1] + bbox[3]) / 2.0

        candidatos = [
            (capa, txt)
            for (x0, y0, x1, y1, capa, txt) in indice
            if x0 - 0.5 <= cx <= x1 + 0.5 and y0 - 0.5 <= cy <= y1 + 0.5
        ]

        if not candidatos:
            return ""

        t = re.sub(r"\s+", "", texto or "")

        if t:
            for capa, txt in candidatos:
                if txt and (
                    t == txt or (len(txt) >= 2 and (txt in t or t in txt))
                ):
                    return capa

        return candidatos[0][0]

    @classmethod
    def _fusionar_signos_sueltos(
        cls,
        unidades: List[Tuple[str, Tuple[float, float, float, float]]],
    ) -> List[Tuple[str, Tuple[float, float, float, float]]]:
        """
        Algunos CAD exportan el signo y el número como líneas de texto
        separadas ("+" y "7.90"). Si una línea es solo un signo y la
        siguiente empieza con número, se fusionan en una sola unidad.
        """
        salida = []
        i = 0

        while i < len(unidades):
            texto, bbox = unidades[i]
            limpio = cls._normalizar_texto_nivel(texto)

            if (
                cls.SIGN_ONLY_PATTERN.match(limpio)
                and i + 1 < len(unidades)
                and cls.STARTS_WITH_NUMBER_PATTERN.match(unidades[i + 1][0].strip())
            ):
                texto2, bbox2 = unidades[i + 1]
                fusion_bbox = (
                    min(bbox[0], bbox2[0]),
                    min(bbox[1], bbox2[1]),
                    max(bbox[2], bbox2[2]),
                    max(bbox[3], bbox2[3]),
                )
                salida.append((limpio + texto2.strip(), fusion_bbox))
                i += 2
                continue

            salida.append((texto, bbox))
            i += 1

        return salida

    @classmethod
    def _evaluar_texto_nivel(
        cls,
        texto: str,
        bbox: Sequence[float],
        capa: str,
        page_number: int,
        niveles: List[Dict[str, Any]],
        candidatos_sin_signo: List[Dict[str, Any]],
        rechazados: List[Dict[str, Any]],
    ) -> None:
        """Decide si una línea de texto es un nivel."""
        if not any(c.isdigit() for c in texto):
            return

        es_cotas = bool(capa) and cls._is_dimension_layer(capa)
        en_niveles = bool(capa) and cls._is_level_layer(capa)

        # Las medidas de cota no son niveles; un texto con signo sí puede serlo.
        if es_cotas and not (
            cls.ACEPTAR_NIVELES_CON_SIGNO_EN_COTAS and cls._texto_tiene_signo(texto)
        ):
            return

        x = (bbox[0] + bbox[2]) / 2.0
        y = (bbox[1] + bbox[3]) / 2.0

        valor = cls._parse_level_text(texto, en_capa_niveles=en_niveles)

        if valor is None:
            if en_niveles:
                if len(rechazados) < cls.NIVEL_RECHAZADOS_MAX:
                    rechazados.append(
                        {"texto": texto[:40], "page": page_number, "x": x, "y": y, "capa": capa}
                    )
            elif not es_cotas and cls.LEVEL_BARE_NUMBER_PATTERN.match(texto.strip()):
                # Número suelto: se decide después según símbolos cercanos.
                candidatos_sin_signo.append(
                    {"texto": texto.strip(), "page": page_number, "x": x, "y": y, "capa": capa}
                )
            return

        if cls._es_duplicado(niveles, valor, x, y, page_number):
            return

        niveles.append(
            cls._create_level(
                level_id=f"p{page_number}-nivel-{len(niveles) + 1:03d}",
                value=valor,
                text=texto,
                x=x,
                y=y,
                page=page_number,
                layer=capa or "LEVELS",
            )
        )

    @classmethod
    def _leer_textos(
        cls,
        page: "fitz.Page",
        page_number: int,
        textos: List[Dict[str, Any]],
        niveles: List[Dict[str, Any]],
        capas_detectadas: set,
        candidatos_sin_signo: Optional[List[Dict[str, Any]]] = None,
        rechazados: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Lee textos y detecta niveles."""
        if candidatos_sin_signo is None:
            candidatos_sin_signo = []
        if rechazados is None:
            rechazados = []

        try:
            contenido = page.get_text("dict")
        except Exception:
            return

        indice_capas = cls._indice_capas_texto(page)

        for entrada in indice_capas:
            if entrada[4]:
                capas_detectadas.add(entrada[4])

        for block_index, block in enumerate(contenido.get("blocks", [])):
            if block.get("type") != 0:
                continue

            lineas_texto: List[str] = []
            unidades: List[Tuple[str, Tuple[float, float, float, float]]] = []

            for line in block.get("lines", []):
                texto = "".join(
                    span.get("text", "") for span in line.get("spans", [])
                ).strip()

                if not texto:
                    continue

                lineas_texto.append(texto)

                bbox = line.get("bbox")

                if bbox:
                    unidades.append((texto, tuple(float(v) for v in bbox)))

            # Une signos sueltos ("+" / "7.90") antes de evaluar niveles.
            for texto, bbox in cls._fusionar_signos_sueltos(unidades):
                capa_linea = cls._capa_de_texto(bbox, indice_capas, texto)

                cls._evaluar_texto_nivel(
                    texto,
                    bbox,
                    capa_linea,
                    page_number,
                    niveles,
                    candidatos_sin_signo,
                    rechazados,
                )

            texto_bloque = "\n".join(lineas_texto)

            if texto_bloque:
                bx = float(block["bbox"][0])
                by = float(block["bbox"][1])

                # La capa del bloque se calcula siempre (antes dependía de
                # la última línea con dígitos y podía quedar sin definir).
                capa_bloque = cls._capa_de_texto(
                    block["bbox"], indice_capas, lineas_texto[0]
                )

                textos.append(
                    {
                        "id": f"p{page_number}-text-{block_index}",
                        "text": texto_bloque[:500],
                        "x": bx,
                        "y": by,
                        "posicion": cls._point_dict(bx, by),
                        "page": page_number,
                        "capa": capa_bloque,
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
                and abs(nivel["valor"] - valor) < 1e-9
                and math.hypot(nivel["x"] - x, nivel["y"] - y)
                < cls.LEVEL_DEDUP_DISTANCE
            ):
                return True

        return False

    @classmethod
    def _rescatar_niveles_por_simbolo(
        cls,
        candidatos: List[Dict[str, Any]],
        level_marks: List[Dict[str, Any]],
        niveles: List[Dict[str, Any]],
    ) -> int:
        """
        Un número suelto sin signo (ej. "3.20") fuera de una capa de niveles
        se acepta como nivel positivo si hay un símbolo de nivel cerca.
        Devuelve la cantidad de niveles rescatados.
        """
        if not candidatos or not level_marks:
            return 0

        rescatados = 0

        for cand in candidatos:
            cercano = any(
                m.get("page") == cand["page"]
                and math.hypot(m["x"] - cand["x"], m["y"] - cand["y"])
                <= cls.NIVEL_SIMBOLO_DISTANCIA
                for m in level_marks
            )

            if not cercano:
                continue

            valor = cls._to_level_value(None, cand["texto"])

            if valor is None:
                continue

            if cls._es_duplicado(niveles, valor, cand["x"], cand["y"], cand["page"]):
                continue

            niveles.append(
                cls._create_level(
                    level_id=f"p{cand['page']}-nivel-{len(niveles) + 1:03d}",
                    value=valor,
                    text=cand["texto"],
                    x=cand["x"],
                    y=cand["y"],
                    page=cand["page"],
                    layer=cand.get("capa") or "LEVELS",
                    origen="texto_cerca_de_simbolo",
                )
            )
            rescatados += 1

        return rescatados

    # =========================================================
    # DRAWINGS
    # =========================================================

    @classmethod
    def _segmentos_de_item(
        cls,
        item: Tuple,
    ) -> List[Tuple[str, Punto, Punto, float]]:
        """Convierte un item PDF en segmentos."""
        tipo = item[0]

        if tipo == "l":
            a, b = item[1], item[2]

            return [
                (
                    "line",
                    (float(a.x), float(a.y)),
                    (float(b.x), float(b.y)),
                    0.98,
                )
            ]

        if tipo in ("re", "qu"):
            if tipo == "re":
                r = item[1]
                pts = [
                    (float(r.x0), float(r.y0)),
                    (float(r.x1), float(r.y0)),
                    (float(r.x1), float(r.y1)),
                    (float(r.x0), float(r.y1)),
                ]
            else:
                q = item[1]
                pts = [
                    (float(q.ul.x), float(q.ul.y)),
                    (float(q.ur.x), float(q.ur.y)),
                    (float(q.lr.x), float(q.lr.y)),
                    (float(q.ll.x), float(q.ll.y)),
                ]

            prefijo = "rect" if tipo == "re" else "quad"

            return [
                (f"{prefijo}-{i}", pts[i], pts[(i + 1) % 4], 0.96)
                for i in range(4)
            ]

        if tipo == "c":
            p1, p2, p3, p4 = [(float(p.x), float(p.y)) for p in item[1:5]]

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
                (f"curve-{i}", puntos[i], puntos[i + 1], 0.90)
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
        roof_segmentos: Dict[int, List[Segmento]],
        aux_segmentos: List[Tuple[int, Segmento]],
        level_marks: List[Dict[str, Any]],
    ) -> None:
        """Procesa un drawing completo."""
        es_roof = cls._is_roof_layer(layer)
        es_aux = cls._is_aux_roof_layer(layer)

        if cls._is_level_symbol_layer(layer):
            rect = drawing.get("rect")

            if rect is not None:
                x = (float(rect.x0) + float(rect.x1)) / 2.0
                y = (float(rect.y0) + float(rect.y1)) / 2.0

                level_marks.append(
                    {
                        "id": f"{drawing_id}-level-symbol",
                        "x": x,
                        "y": y,
                        "posicion": cls._point_dict(x, y),
                        "page": page_number,
                        "capa": layer,
                        "tipo": "simbolo",
                    }
                )

        def registrar(sufijo_id: str, a: Punto, b: Punto, confianza: float):
            lineas.append(
                {
                    "id": f"{drawing_id}-{sufijo_id}",
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
                roof_segmentos[page_number].append((a, b))
            elif es_aux:
                aux_segmentos.append((page_number, (a, b)))

        subpaths: List[Tuple[Punto, Punto]] = []
        actual: Optional[Tuple[Punto, Punto]] = None

        for item_index, item in enumerate(drawing.get("items", [])):
            if not item:
                continue

            tipo = item[0]

            if tipo == "c" and not (es_roof or es_aux):
                continue

            try:
                segmentos = cls._segmentos_de_item(item)
            except Exception:
                continue

            for sufijo, a, b, confianza in segmentos:
                registrar(f"i{item_index}-{sufijo}", a, b, confianza)

            if tipo in ("l", "c") and segmentos:
                inicio = segmentos[0][1]
                fin = segmentos[-1][2]

                if actual and math.dist(actual[1], inicio) <= 1e-3:
                    actual = (actual[0], fin)
                else:
                    if actual:
                        subpaths.append(actual)

                    actual = (inicio, fin)

        if actual:
            subpaths.append(actual)

        if es_roof or es_aux:
            cerrar = bool(drawing.get("closePath")) or (
                es_roof and "f" in str(drawing.get("type") or "")
            )

            if cerrar:
                for n, (inicio, fin) in enumerate(subpaths):
                    if math.dist(inicio, fin) > 1e-6:
                        registrar(f"close-{n}", fin, inicio, 0.90)

    # =========================================================
    # POLÍGONOS ROOF
    # =========================================================

    @staticmethod
    def _unificar_extremos(
        segmentos: Sequence[Segmento],
        tol: float,
    ) -> List[Segmento]:
        """Junta extremos próximos."""
        celdas: Dict[Tuple[int, int], List[Punto]] = defaultdict(list)

        def unir(p: Punto) -> Punto:
            cx = int(p[0] // tol)
            cy = int(p[1] // tol)

            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for q in celdas.get((cx + dx, cy + dy), ()):
                        if abs(q[0] - p[0]) <= tol and abs(q[1] - p[1]) <= tol:
                            return q

            celdas[(cx, cy)].append(p)

            return p

        salida = []

        for a, b in segmentos:
            a2 = unir(a)
            b2 = unir(b)

            if a2 != b2:
                salida.append((a2, b2))

        return salida

    @staticmethod
    def _segmentos_de_geometria(geometria) -> List[Segmento]:
        partes = list(geometria.geoms) if hasattr(geometria, "geoms") else [geometria]

        segmentos = []

        for parte in partes:
            coords = list(getattr(parte, "coords", []))

            for i in range(len(coords) - 1):
                a = (float(coords[i][0]), float(coords[i][1]))
                b = (float(coords[i + 1][0]), float(coords[i + 1][1]))

                if a != b:
                    segmentos.append((a, b))

        return segmentos

    @classmethod
    def _cerrar_huecos(
        cls,
        segmentos: Sequence[Segmento],
        snap_tol: Optional[float] = None,
        gap_tol: Optional[float] = None,
    ) -> Tuple[List[Segmento], int]:
        """
        Prepara líneas ROOF para polygonize.

        `snap_tol` y `gap_tol` están en las unidades de las coordenadas de
        entrada. Por defecto usan las constantes de clase (pensadas para
        puntos PDF); un DXF en metros debería pasar valores propios, porque
        1.5 unidades serían 1.5 m y uniría líneas que no deben unirse.
        """
        if snap_tol is None:
            snap_tol = cls.ROOF_SNAP_TOLERANCE

        if gap_tol is None:
            gap_tol = cls.ROOF_GAP_TOLERANCE

        segmentos = cls._unificar_extremos(segmentos, snap_tol)

        if not segmentos:
            return [], 0

        try:
            piezas = cls._segmentos_de_geometria(
                unary_union([LineString(s) for s in segmentos])
            )
        except Exception:
            return list(segmentos), 0

        def clave(p: Punto) -> Tuple[float, float]:
            return (round(p[0], 6), round(p[1], 6))

        grado: Counter = Counter()

        for a, b in piezas:
            grado[clave(a)] += 1
            grado[clave(b)] += 1

        celda = max(gap_tol * 4.0, 8.0)

        indice: Dict[Tuple[int, int], List[int]] = defaultdict(list)

        for i, (a, b) in enumerate(piezas):
            for cx in range(int(min(a[0], b[0]) // celda), int(max(a[0], b[0]) // celda) + 1):
                for cy in range(int(min(a[1], b[1]) // celda), int(max(a[1], b[1]) // celda) + 1):
                    indice[(cx, cy)].append(i)

        cortes: Dict[int, List[Punto]] = defaultdict(list)
        conectores = []

        for i, (a, b) in enumerate(piezas):
            propios = {clave(a), clave(b)}

            for p in (a, b):
                if grado[clave(p)] != 1:
                    continue

                mejor = None
                vistos = {i}

                for cx in range(int((p[0] - gap_tol) // celda), int((p[0] + gap_tol) // celda) + 1):
                    for cy in range(int((p[1] - gap_tol) // celda), int((p[1] + gap_tol) // celda) + 1):
                        for j in indice.get((cx, cy), ()):
                            if j in vistos:
                                continue

                            vistos.add(j)

                            c, d = piezas[j]

                            if clave(c) in propios or clave(d) in propios:
                                continue

                            q, dist = NivelesUtils.punto_mas_cercano_en_segmento(p, c, d)

                            if dist <= gap_tol and (mejor is None or dist < mejor[0]):
                                mejor = (dist, j, q)

                if mejor is None:
                    continue

                _, j, q = mejor
                c, d = piezas[j]

                if math.dist(q, c) <= snap_tol:
                    q = c
                elif math.dist(q, d) <= snap_tol:
                    q = d
                else:
                    cortes[j].append(q)

                if math.dist(p, q) > 1e-9:
                    conectores.append((p, q))

        resultado = []

        for j, (a, b) in enumerate(piezas):
            if j not in cortes:
                resultado.append((a, b))
                continue

            cadena = [a] + sorted(set(cortes[j]), key=lambda q: math.dist(a, q)) + [b]

            for k in range(len(cadena) - 1):
                if cadena[k] != cadena[k + 1]:
                    resultado.append((cadena[k], cadena[k + 1]))

        resultado.extend(conectores)

        return resultado, len(conectores)

    @classmethod
    def _limpiar_colineales(cls, puntos: List[Punto]) -> List[Punto]:
        """Elimina vértices colineales."""
        pts = list(puntos)
        i = 0

        while i < len(pts) and len(pts) > 3:
            a = pts[i - 1]
            b = pts[i]
            c = pts[(i + 1) % len(pts)]

            _, d = NivelesUtils.punto_mas_cercano_en_segmento(b, a, c)

            if d <= cls.ROOF_COLLINEAR_TOLERANCE:
                pts.pop(i)
                i = max(i - 1, 0)
            else:
                i += 1

        return pts

    @classmethod
    def _build_roof_polygons(
        cls,
        roof_segmentos: Dict[int, List[Segmento]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Construye polígonos desde ROOF."""
        poligonos = []
        extremos_abiertos = []
        total_abiertos = 0
        total_conectores = 0
        contador = 0

        for page_number in sorted(roof_segmentos):
            segmentos = roof_segmentos[page_number]

            if not segmentos:
                continue

            cerrados, conectores = cls._cerrar_huecos(segmentos)
            total_conectores += conectores

            try:
                piezas = [LineString(s) for s in cerrados]
                unido = unary_union(piezas)
                lista = list(unido.geoms) if hasattr(unido, "geoms") else [unido]
                caras, _cortes, dangles, _invalidos = polygonize_full(lista)
            except Exception:
                continue

            for dangle in dangles.geoms:
                total_abiertos += 1

                if len(extremos_abiertos) < 100:
                    c = list(dangle.coords)

                    extremos_abiertos.append(
                        {
                            "page": page_number,
                            "x1": float(c[0][0]),
                            "y1": float(c[0][1]),
                            "x2": float(c[-1][0]),
                            "y2": float(c[-1][1]),
                        }
                    )

            ordenadas = sorted(
                (c for c in caras.geoms if not c.is_empty),
                key=lambda c: (round(c.bounds[1], 3), round(c.bounds[0], 3)),
            )

            for cara in ordenadas:
                area = float(cara.area)

                if area < cls.ROOF_MIN_AREA:
                    continue

                coords = [
                    (float(x), float(y)) for x, y in cara.exterior.coords[:-1]
                ]

                coords = cls._limpiar_colineales(coords)

                if len(coords) < 3:
                    continue

                contador += 1

                minx, miny, maxx, maxy = cara.bounds

                poligonos.append(
                    {
                        "id": f"roof_{contador:03d}",
                        "tipo": "poligono",
                        "capa": "ROOF",
                        "origen": "pdf",
                        "page": page_number,
                        "puntos": [{"x": x, "y": y} for x, y in coords],
                        "area": area,
                        "bounding_box": {
                            "min_x": float(minx),
                            "min_y": float(miny),
                            "max_x": float(maxx),
                            "max_y": float(maxy),
                        },
                        "centro": {
                            "x": float(cara.centroid.x),
                            "y": float(cara.centroid.y),
                        },
                        "niveles": [],
                        "nivel_bajo": None,
                        "nivel_medio": None,
                        "nivel_alto": None,
                        "pendiente": None,
                        "tipo_cubierta": "pendiente_por_resolver",
                    }
                )

        diagnostico = {
            "roof_conectores_agregados": total_conectores,
            "roof_extremos_abiertos": total_abiertos,
            "roof_extremos_abiertos_muestra": extremos_abiertos,
        }

        return poligonos, diagnostico

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
            xs.extend([float(line["x1"]), float(line["x2"])])
            ys.extend([float(line["y1"]), float(line["y2"])])

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

        IMPORTANTE: la asociación de niveles ocurre antes de convertir a
        metros. Esto mantiene intacta la lógica existente de NivelesUtils.
        """
        lineas = []
        roof_segmentos = defaultdict(list)
        aux_segmentos = []
        niveles_detectados = []
        level_marks = []
        textos = []
        capas_detectadas = set()
        candidatos_sin_signo: List[Dict[str, Any]] = []
        niveles_rechazados: List[Dict[str, Any]] = []

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
                candidatos_sin_signo,
                niveles_rechazados,
            )

            # ÚNICO recorrido de drawings.
            for drawing_index, drawing in enumerate(page.get_drawings()):
                layer = cls._normalize_layer(drawing.get("layer"))

                if layer:
                    capas_detectadas.add(layer)

                cls._procesar_drawing(
                    drawing,
                    drawing_id=f"p{page_number}-d{drawing_index}",
                    page_number=page_number,
                    layer=layer,
                    lineas=lineas,
                    roof_segmentos=roof_segmentos,
                    aux_segmentos=aux_segmentos,
                    level_marks=level_marks,
                )

        # -----------------------------------------------------
        # RESCATE DE NIVELES SIN SIGNO CERCA DE SÍMBOLOS
        # -----------------------------------------------------

        rescatados = cls._rescatar_niveles_por_simbolo(
            candidatos_sin_signo,
            level_marks,
            niveles_detectados,
        )

        # -----------------------------------------------------
        # POLÍGONOS
        # -----------------------------------------------------

        poligonos, diagnostico = cls._build_roof_polygons(roof_segmentos)

        diagnostico["niveles_rescatados_por_simbolo"] = rescatados
        diagnostico["niveles_rechazados_en_capa_niveles"] = niveles_rechazados

        # -----------------------------------------------------
        # NIVELES -> POLÍGONOS
        #
        # NO TOCAR.
        # -----------------------------------------------------

        niveles, descartados = NivelesUtils.asociar_niveles_automaticamente(
            poligonos,
            niveles_detectados,
            cls.NIVEL_DISTANCIA_MAXIMA,
        )

        NivelesUtils.reconstruir_niveles_poligonos(poligonos, niveles)

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
            for page, segmentos in roof_segmentos.items()
            for a, b in segmentos
        ]

        aux_roof = [
            {
                "id": f"aux_roof_{index:04d}",
                "tipo": "linea_pendiente",
                "capa": "AUX_ROOF",
                "page": page,
                "x1": a[0],
                "y1": a[1],
                "x2": b[0],
                "y2": b[1],
            }
            for index, (page, (a, b)) in enumerate(aux_segmentos, start=1)
        ]

        # -----------------------------------------------------
        # MODELO ANTES DE ESCALA
        # -----------------------------------------------------

        modelo = {
            "version": "0.5.0",
            "units": "pdf-points",
            "coordinate_system": "pdf-native",
            "pages": len(doc),
            "capas": sorted(capas_detectadas),
            "lineas": lineas,
            "roof_lines": roof_lines,
            "aux_roof": aux_roof,
            "poligonos": poligonos,
            "niveles": niveles,
            "cotas_altura": niveles,
            "niveles_descartados": descartados[:500],
            "level_marks": level_marks,
            "textos": textos[:1000],
            "bounding_box": cls._calculate_bounding_box(lineas),
            "diagnostico": diagnostico,
        }

        # -----------------------------------------------------
        # ESCALA
        # -----------------------------------------------------

        escala = cls._detectar_factor_escala(lineas, textos)

        # -----------------------------------------------------
        # CONVERSIÓN FINAL
        # -----------------------------------------------------

        modelo = cls.convertir_modelo_a_metros(modelo, doc, escala)

        # -----------------------------------------------------
        # RESUMEN FINAL
        # -----------------------------------------------------

        modelo["resumen"] = {
            "cantidad_lineas": len(modelo["lineas"]),
            "cantidad_lineas_roof": len(modelo["roof_lines"]),
            "cantidad_lineas_aux_roof": len(modelo["aux_roof"]),
            "cantidad_poligonos_roof": len(modelo["poligonos"]),
            "cantidad_niveles_detectados": len(niveles_detectados),
            "cantidad_niveles_rescatados_por_simbolo": rescatados,
            "cantidad_niveles": len(modelo["niveles"]),
            "cantidad_niveles_descartados": len(descartados),
            "cantidad_simbolos_nivel": len(modelo["level_marks"]),
            "cantidad_textos": len(modelo["textos"]),
            "unidad_geometria": "metros",
            "factor_escala_xy": modelo["scale"]["factor_xy"],
            "origen_coordenadas": "bounding_box",
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
            raise ValueError("El archivo PDF está vacío.")

        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception as exc:
            raise ValueError(f"No se pudo abrir el PDF '{filename}': {exc}")

        if doc.page_count == 0:
            doc.close()
            raise ValueError("El PDF no contiene páginas.")

        return doc