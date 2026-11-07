"""app.services.memoria_pdf_service

Genera el PDF final de la Memoria Descriptiva del SPDA con estilo técnico:

  · Portada con logo FARADYNE, imagen principal y datos del proyecto.
  · Índice (contenido, tablas y figuras) con enlaces y marcadores.
  · Cuerpo en A4 con encabezado y pie, tablas y figuras con formato APA
    (rótulo en negrita, título en cursiva arriba, reglas horizontales, «Nota.» abajo).
  · Solo las imágenes que el usuario eligió en la vista previa.

Usa únicamente pymupdf (ya está en requirements.txt). Las fuentes IBM Plex
(licencia OFL) están en app/assets/fonts. Si existe app/assets/logo_faradyne.png se usa
como logo; si no, se dibuja la marca vectorial (rayo + "FARADYNE").

El servicio no consulta la base ni recalcula nada: recibe los datos ya armados por el
endpoint de vista previa (los mismos que ve el usuario).
"""
from __future__ import annotations

import base64
import binascii
import html
import io
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import pymupdf as fitz
except ImportError:  # pymupdf anterior a 1.24.3
    import fitz  # type: ignore

# ──────────────────────────────────────────────────────────────────────────────
# Recursos y constantes de diseño
# ──────────────────────────────────────────────────────────────────────────────

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
LOGO_PATH = ASSETS_DIR / "logo_faradyne.png"  # opcional

BRAND = "#1B6EB9"      # azul de la app
INK = "#111827"
TEXT = "#1F2937"
MUTED = "#6B7280"
RULE = "#CBD5E1"
PANEL = "#F3F6FA"

A4 = fitz.paper_rect("a4")
MARGEN_IZQ = 56.0
MARGEN_DER = 56.0
MARGEN_SUP = 84.0
MARGEN_INF = 66.0
ANCHO_UTIL = A4.width - MARGEN_IZQ - MARGEN_DER

MAX_PAGINAS_CUERPO = 80
MAX_IMAGENES = 8
MAX_BYTES_IMAGEN = 20 * 1024 * 1024
MAX_LADO_IMAGEN = 9000

ORDEN_IMAGENES = ["plano", "iso", "iso_der", "caballera", "militar", "front", "top", "side"]
TITULOS_IMAGEN = {
    "plano": "Plano base 2D con los mástiles captores",
    "iso": "Modelo 3D con cobertura SPDA: vista isométrica",
    "iso_der": "Modelo 3D con cobertura SPDA: vista isométrica derecha",
    "caballera": "Modelo 3D con cobertura SPDA: perspectiva caballera",
    "militar": "Modelo 3D con cobertura SPDA: perspectiva militar",
    "front": "Modelo 3D con cobertura SPDA: vista frontal",
    "top": "Modelo 3D con cobertura SPDA: vista en planta",
    "side": "Modelo 3D con cobertura SPDA: vista lateral",
}
NOTAS_VISTA = {
    "iso": "Vista isométrica del modelo 3D, desde la esquina delantera derecha.",
    "iso_der": "Vista isométrica del modelo 3D, desde la esquina posterior derecha.",
    "caballera": ("Proyección oblicua (caballera): el frente se representa en verdadera "
                  "magnitud y la profundidad a 45°, con coeficiente de reducción 1."),
    "militar": ("Proyección oblicua (militar): la planta se representa en verdadera "
                "magnitud, girada 30°, y las alturas en vertical a escala real."),
    "front": "Vista frontal del modelo 3D.",
    "top": "Vista en planta del modelo 3D.",
    "side": "Vista lateral del modelo 3D.",
}
NIVEL_LABELS = {"I+": "Nivel I+", "I": "Nivel I", "II": "Nivel II", "III": "Nivel III", "IV": "Nivel IV"}

# Factores de riesgo del Anexo E (Tablas E.1 a E.5): (clave, nombre, tabla, {valor: criterio}).
FACTORES_ANEXO_E = [
    ("a", "A · Ocupación", "E.1", {
        0.3: "Casas u otras estructuras de porte equivalente",
        0.7: "Casas con antena exterior",
        1.0: "Fábricas, oficinas y laboratorios",
        1.2: "Oficinas, hoteles, departamentos, residenciales",
        1.3: "Locales de afluencia de público",
        1.7: "Escuelas, hospitales, actividades múltiples"}),
    ("b", "B · Construcción", "E.2", {
        0.2: "Acero recubierto, cubierta no metálica",
        0.4: "Hormigón armado, cubierta no metálica",
        0.8: "Acero u hormigón armado con cubierta metálica",
        1.0: "Mampostería o concreto simple, sin cubierta metálica ni paja",
        1.7: "Madera, mampostería o concreto simple, con cubierta metálica",
        2.0: "Cualquier estructura con techo de paja"}),
    ("c", "C · Contenido", "E.3", {
        0.3: "Residencias, oficinas, fábricas sin objetos de valor",
        0.8: "Industrial o agrícola con objetos de valor",
        1.0: "Subestaciones, centrales, telefónicas, radio",
        1.3: "Industrias estratégicas, museos, monumentos",
        1.7: "Escuelas, hospitales, guarderías, afluencia pública"}),
    ("d", "D · Localización", "E.4", {
        0.4: "Área con estructuras o árboles iguales o más altos",
        1.0: "Área con pocas estructuras de altura similar",
        2.0: "Estructura aislada o mucho más alta que su entorno"}),
    ("e", "E · Topografía", "E.5", {
        0.3: "Planicie",
        1.0: "Elevaciones moderadas, colinas",
        1.3: "Montañas de 300 a 900 m",
        1.7: "Montañas de más de 900 m"}),
]
ESTADO_CUBIERTA = {
    "protegido": ("Protegido", "#047857"),
    "parcial": ("Parcial", "#B45309"),
    "desprotegido": ("Desprotegido", "#B91C1C"),
}


# ──────────────────────────────────────────────────────────────────────────────
# Formato (es-AR)
# ──────────────────────────────────────────────────────────────────────────────

def _num(v: Any) -> Optional[float]:
    try:
        if v is None or isinstance(v, bool):
            return None
        x = float(v)
        return x if x == x and x not in (float("inf"), float("-inf")) else None
    except (TypeError, ValueError):
        return None


def _n(v: Any, dec: int = 2, sufijo: str = "") -> str:
    """1234.5 -> '1.234,50'. Sin dato: '—'."""
    x = _num(v)
    if x is None:
        return "—"
    s = f"{x:,.{dec}f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return f"{s}{sufijo}"


def _pct(v: Any, dec: int = 2) -> str:
    x = _num(v)
    return "—" if x is None else f"{_n(x, dec)} %"


def _fecha(v: Any) -> str:
    if v is None or v == "":
        return "No disponible"
    if isinstance(v, (date, datetime)):
        return v.strftime("%d/%m/%Y")
    try:
        return datetime.fromisoformat(str(v)[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return str(v)


def _t(v: Any, fallback: str = "No disponible") -> str:
    """Texto escapado para HTML; vacío -> fallback."""
    if v is None or str(v).strip() == "":
        return html.escape(fallback)
    return html.escape(str(v).strip())


def _rgb(hex_: str) -> Tuple[float, float, float]:
    h = hex_.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


# ──────────────────────────────────────────────────────────────────────────────
# Imágenes recibidas del frontend
# ──────────────────────────────────────────────────────────────────────────────

_DATA_URL = re.compile(r"^data:image/(png|jpeg|jpg);base64,(?P<b64>.+)$", re.DOTALL)


def decodificar_imagenes(imagenes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Valida y decodifica las imágenes (dataURL base64) que eligió el usuario.

    Devuelve una lista ordenada como irán en el documento (plano y luego las vistas 3D),
    sin repetidos. Lanza ValueError con un mensaje claro si alguna no es válida.
    """
    if len(imagenes) > MAX_IMAGENES:
        raise ValueError(f"Se pueden incluir hasta {MAX_IMAGENES} imágenes.")

    por_clave: Dict[str, Dict[str, Any]] = {}
    for img in imagenes:
        clave = img.get("clave")
        if clave not in TITULOS_IMAGEN:
            raise ValueError(f"Imagen desconocida: {clave!r}.")
        m = _DATA_URL.match(img.get("data_url") or "")
        if not m:
            raise ValueError(f"La imagen «{clave}» no llegó en formato PNG/JPEG en base64.")
        try:
            data = base64.b64decode(m.group("b64"), validate=True)
        except (binascii.Error, ValueError):
            raise ValueError(f"La imagen «{clave}» está corrupta (base64 inválido).") from None
        if len(data) > MAX_BYTES_IMAGEN:
            raise ValueError(f"La imagen «{clave}» es demasiado pesada.")
        try:
            pix = fitz.Pixmap(data)
            ancho, alto = pix.width, pix.height
        except Exception:
            raise ValueError(f"La imagen «{clave}» no se pudo leer.") from None
        if not (0 < ancho <= MAX_LADO_IMAGEN and 0 < alto <= MAX_LADO_IMAGEN):
            raise ValueError(f"La imagen «{clave}» tiene un tamaño no permitido.")
        por_clave[clave] = {
            "clave": clave,
            "titulo": TITULOS_IMAGEN[clave],
            "bytes": data,
            "ancho": ancho,
            "alto": alto,
            "ext": "png" if m.group(1) == "png" else "jpg",
        }
    return [por_clave[k] for k in ORDEN_IMAGENES if k in por_clave]


# ──────────────────────────────────────────────────────────────────────────────
# Fuentes y dibujo directo (portada, índice, encabezado y pie)
# ──────────────────────────────────────────────────────────────────────────────

class _Fuentes:
    def __init__(self) -> None:
        def f(nombre: str) -> "fitz.Font":
            return fitz.Font(fontfile=str(FONTS_DIR / nombre))
        self.sans = f("IBMPlexSans-Regular.ttf")
        self.sans_med = f("IBMPlexSans-Medium.ttf")
        self.sans_semi = f("IBMPlexSans-SemiBold.ttf")
        self.cond_semi = f("IBMPlexSansCondensed-SemiBold.ttf")
        self.cond_bold = f("IBMPlexSansCondensed-Bold.ttf")
        self.mono = f("IBMPlexMono-Regular.ttf")


def _ancho(font: "fitz.Font", texto: str, size: float, tracking: float = 0.0) -> float:
    return font.text_length(texto, fontsize=size) + tracking * max(len(texto) - 1, 0)


def _dibujar(page: "fitz.Page", x: float, y: float, texto: str, font: "fitz.Font", size: float,
             color: str = INK, tracking: float = 0.0, derecha: bool = False,
             morph: Optional[Tuple[Any, Any]] = None) -> None:
    """Escribe `texto` con la base en (x, y). `derecha` alinea el final del texto en x."""
    if not texto:
        return
    if derecha:
        x -= _ancho(font, texto, size, tracking)
    tw = fitz.TextWriter(page.rect)
    if tracking:
        cx = x
        for ch in texto:
            tw.append((cx, y), ch, font=font, fontsize=size)
            cx += font.text_length(ch, fontsize=size) + tracking
    else:
        tw.append((x, y), texto, font=font, fontsize=size)
    tw.write_text(page, color=_rgb(color), morph=morph)


def _envolver(font: "fitz.Font", texto: str, size: float, ancho: float) -> List[str]:
    lineas: List[str] = []
    actual = ""
    for palabra in texto.split():
        prueba = f"{actual} {palabra}".strip()
        if not actual or font.text_length(prueba, fontsize=size) <= ancho:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas


def _parrafo(page: "fitz.Page", x: float, y: float, ancho: float, texto: str, font: "fitz.Font",
             size: float, color: str = TEXT, interlineado: float = 1.42) -> float:
    for linea in _envolver(font, texto, size, ancho):
        _dibujar(page, x, y, linea, font, size, color)
        y += size * interlineado
    return y


def _linea(page: "fitz.Page", x0: float, y0: float, x1: float, y1: float,
           color: str = RULE, ancho: float = 0.6, punteada: bool = False) -> None:
    page.draw_line((x0, y0), (x1, y1), color=_rgb(color), width=ancho,
                   dashes="[0.6 2.4] 0" if punteada else None)


def _dibujar_logo(page: "fitz.Page", fuentes: _Fuentes, x: float, y: float, alto: float,
                  derecha: bool = False) -> float:
    """Logo FARADYNE con la esquina superior izquierda en (x, y). Devuelve el ancho usado.
    Con derecha=True, `x` es el borde derecho."""
    if LOGO_PATH.is_file():
        pix = fitz.Pixmap(str(LOGO_PATH))
        ancho = alto * pix.width / max(pix.height, 1)
        x0 = x - ancho if derecha else x
        page.insert_image(fitz.Rect(x0, y, x0 + ancho, y + alto), filename=str(LOGO_PATH),
                          keep_proportion=True)
        return ancho

    size = alto * 0.98
    tracking = size * 0.07
    texto = "FARADYNE"
    ancho_texto = _ancho(fuentes.cond_bold, texto, size, tracking)
    lado = alto  # el rayo ocupa un cuadrado de `alto`
    sep = alto * 0.28
    ancho = lado + sep + ancho_texto
    x0 = x - ancho if derecha else x

    # Rayo (misma silueta que el ícono del encabezado de la app)
    s = lado / 24.0
    pts = [(13, 2), (3, 14), (12, 14), (11, 22), (21, 10), (12, 10)]
    sh = page.new_shape()
    sh.draw_polyline([fitz.Point(x0 + px * s, y + py * s) for px, py in pts])
    sh.finish(fill=_rgb(BRAND), color=_rgb(BRAND), width=alto * 0.05, closePath=True,
              lineJoin=1, lineCap=1)
    sh.commit()

    cap = size * 0.698  # altura de mayúscula de IBM Plex Sans Condensed
    base = y + alto / 2 + cap / 2
    _dibujar(page, x0 + lado + sep, base, texto, fuentes.cond_bold, size, INK, tracking)
    return ancho


# ──────────────────────────────────────────────────────────────────────────────
# Cuerpo (HTML + CSS → Story de pymupdf)
# ──────────────────────────────────────────────────────────────────────────────

CSS = f"""
@font-face {{font-family: plex; src: url(IBMPlexSans-Regular.ttf);}}
@font-face {{font-family: plex; font-weight: bold; src: url(IBMPlexSans-SemiBold.ttf);}}
@font-face {{font-family: plex; font-style: italic; src: url(IBMPlexSans-Italic.ttf);}}
@font-face {{font-family: plex; font-weight: bold; font-style: italic; src: url(IBMPlexSans-BoldItalic.ttf);}}
@font-face {{font-family: plexc; src: url(IBMPlexSansCondensed-Medium.ttf);}}
@font-face {{font-family: plexc; font-weight: bold; src: url(IBMPlexSansCondensed-Bold.ttf);}}
@font-face {{font-family: plexm; src: url(IBMPlexMono-Regular.ttf);}}
@font-face {{font-family: plexm; font-weight: bold; src: url(IBMPlexMono-Medium.ttf);}}

body {{ font-family: plex; font-size: 9pt; line-height: 1.42; color: {TEXT}; }}
p {{ margin: 0 0 6pt 0; text-align: left; }}
h1 {{ font-family: plexc; font-weight: bold; font-size: 19pt; line-height: 1.1; color: {INK};
      margin: 0 0 3pt 0; }}
.kicker {{ font-family: plexc; font-weight: bold; font-size: 8pt; color: {BRAND}; margin: 0 0 1pt 0; }}
.lead {{ font-size: 9pt; color: {MUTED}; margin: 0 0 9pt 0; }}
.pb {{ page-break-before: always; }}
h2 {{ font-family: plexc; font-weight: bold; font-size: 11pt; color: {INK}; margin: 11pt 0 5pt 0; }}

.cap {{ margin: 8pt 0 3pt 0; font-size: 9pt; color: {INK}; }}
.capn {{ font-weight: bold; }}
.capt {{ font-style: italic; }}
.nota {{ font-size: 7.6pt; color: {MUTED}; margin: 3pt 0 10pt 0; }}

table.apa {{ width: 100%; border-collapse: collapse; margin: 0; }}
table.apa th {{ font-weight: bold; text-align: left; font-size: 8.4pt; color: {INK};
               border-top: 1.2pt solid {INK}; border-bottom: 0.7pt solid {INK};
               padding: 3.2pt 5pt; }}
table.apa td {{ font-size: 8.6pt; padding: 3pt 5pt; vertical-align: top; }}
table.apa tr.ult td {{ border-bottom: 1.2pt solid {INK}; }}
table.apa th.r, table.apa td.r {{ text-align: right; }}
table.apa th.c, table.apa td.c {{ text-align: center; }}
td.mono {{ font-family: plexm; font-size: 8.2pt; }}
td.k {{ color: {MUTED}; }}

table.kpi {{ width: 100%; border-collapse: collapse; margin: 2pt 0 4pt 0; }}
/* Sin background-color: MuPDF repinta los fondos de celda en las páginas siguientes (barras
   fantasma). La tarjeta se marca con borde superior de color y una línea fina abajo. */
table.kpi td {{ border-top: 2pt solid {BRAND}; border-bottom: 0.6pt solid {RULE}; padding: 5pt 8pt; width: 32%; }}
table.kpi td.sp {{ border-top: 0pt solid #ffffff; border-bottom: 0pt solid #ffffff; width: 2%; padding: 0; }}
.kl {{ font-family: plexc; font-weight: bold; font-size: 7.4pt; color: {MUTED}; }}
.kv {{ font-family: plexc; font-weight: bold; font-size: 17pt; line-height: 1.15; color: {INK}; }}

table.fig {{ width: 100%; border-collapse: collapse; }}
table.fig > tr > td {{ padding: 0; }}
table.frame {{ width: 100%; border-collapse: collapse; }}
table.frame td {{ border: 0.6pt solid {RULE}; padding: 3pt; text-align: center; background-color: #ffffff; }}

.aviso {{ font-size: 8.4pt; color: #92400E; margin: 0 0 3pt 0; }}
.ok {{ font-size: 8.4pt; color: #047857; margin: 4pt 0 0 0; }}
.nd {{ font-size: 8.6pt; color: {MUTED}; font-style: italic; }}

.firma td {{ padding-top: 34pt; font-size: 8pt; color: {MUTED}; border-top: 0pt solid #ffffff; }}
.firma td.l {{ border-top: 0.8pt solid {INK}; }}
.decl {{ font-size: 8.8pt; text-align: justify; margin: 3pt 0 0 0; }}
"""


class _Numeracion:
    """Numeración correlativa de tablas y figuras + índice para la tabla de contenido."""

    def __init__(self) -> None:
        self.t = 0
        self.f = 0
        self.indice_tablas: List[Tuple[str, str, str]] = []   # (id, rótulo, título)
        self.indice_figuras: List[Tuple[str, str, str]] = []

    def tabla(self, titulo: str) -> str:
        self.t += 1
        id_ = f"tab{self.t}"
        self.indice_tablas.append((id_, f"Tabla {self.t}", titulo))
        return (f'<div class="cap" id="{id_}"><span class="capn">Tabla {self.t}</span><br/>'
                f'<span class="capt">{html.escape(titulo)}</span></div>')

    def figura(self, titulo: str) -> Tuple[str, str]:
        self.f += 1
        id_ = f"fig{self.f}"
        self.indice_figuras.append((id_, f"Figura {self.f}", titulo))
        cab = (f'<div class="cap" id="{id_}"><span class="capn">Figura {self.f}</span><br/>'
               f'<span class="capt">{html.escape(titulo)}</span></div>')
        return cab, id_


def _tabla_apa(encabezados: List[Tuple[str, str, str]], filas: List[List[Tuple[str, str]]]) -> str:
    """encabezados: (texto, clase, ancho%). filas: lista de [(html_celda, clase), ...].

    Los anchos se normalizan para que las columnas sumen SIEMPRE 100 %: las que no traen
    ancho se reparten lo que falta. Es importante: en MuPDF, declarar el ancho de una sola
    columna hace que esa columna colapse a su ancho mínimo cuando otra tiene valores largos
    (las etiquetas se partían en 4 líneas).
    """
    conocidos = [float(w.rstrip("%")) for _, _, w in encabezados if w]
    libres = sum(1 for _, _, w in encabezados if not w)
    resto = max(100.0 - sum(conocidos), 0.0)
    por_libre = resto / libres if libres else 0.0
    th = ""
    for txt, c, w in encabezados:
        ancho = float(w.rstrip("%")) if w else por_libre
        estilo = f' style="width:{ancho:.1f}%"' if ancho else ""
        th += f'<th class="{c}"{estilo}>{html.escape(txt)}</th>'
    cuerpo = []
    for i, fila in enumerate(filas):
        cls = ' class="ult"' if i == len(filas) - 1 else ""
        celdas = "".join(f'<td class="{c}">{h}</td>' for h, c in fila)
        cuerpo.append(f"<tr{cls}>{celdas}</tr>")
    return f'<table class="apa"><tr>{th}</tr>{"".join(cuerpo)}</table>'


ANCHO_MARCO = ANCHO_UTIL - 8.0   # ancho útil dentro del marco (borde + relleno de la celda)
ALTO_MAX_FIGURA = 232.0          # alto máximo de una figura, para que entren dos vistas por página


MAX_FILAS_JUNTAS = 14   # tablas de hasta N filas no se parten entre páginas (rótulo + tabla juntos)


def _tabla_rotulada(num: _Numeracion, titulo: str, encabezados: List[Tuple[str, str, str]],
                    filas: List[List[Tuple[str, str]]]) -> str:
    """Rótulo «Tabla N» + tabla APA. Si la tabla es corta se mete en una celda que no se
    parte, así el rótulo no queda huérfano al pie de una página."""
    cab = num.tabla(titulo)
    tabla = _tabla_apa(encabezados, filas)
    if len(filas) <= MAX_FILAS_JUNTAS:
        return f'<table class="fig"><tr><td>{cab}{tabla}</td></tr></table>'
    return cab + tabla


def _bloque_imagen(num: _Numeracion, img: Dict[str, Any], nota: str) -> str:
    """Figura APA: rótulo, imagen enmarcada y nota, todo dentro de una sola celda.

    · El tamaño se da en pt, calculado con la proporción real de la imagen: MuPDF no
      resuelve porcentajes en <img> y la imagen se salía de la página.
    · Rótulo + imagen + nota viven en la MISMA celda de tabla, que no se parte entre
      páginas, para que el rótulo «Figura N» no quede huérfano al pie.
    """
    cab, _ = num.figura(img["titulo"])
    proporcion = img["ancho"] / max(img["alto"], 1)
    ancho = ANCHO_MARCO if img["clave"] == "plano" else ANCHO_MARCO * 0.8
    alto = ancho / proporcion
    if alto > ALTO_MAX_FIGURA:
        alto = ALTO_MAX_FIGURA
        ancho = alto * proporcion
    return (
        '<table class="fig"><tr><td>'
        f'{cab}'
        f'<table class="frame"><tr><td><img src="img_{img["clave"]}.{img["ext"]}" '
        f'style="width:{ancho:.1f}pt; height:{alto:.1f}pt"/></td></tr></table>'
        f'<p class="nota"><i>Nota.</i> {html.escape(nota)}</p>'
        '</td></tr></table>'
    )


def _factores_de(nivel: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """Factores A–E guardados con el nivel. Acepta {factores|factores_riesgo|factor_a_e: {a..e}}
    o columnas sueltas factor_a … factor_e."""
    crudo = nivel.get("factores") or nivel.get("factores_riesgo") or nivel.get("factor_a_e") or {}
    out: Dict[str, Optional[float]] = {}
    for k in "abcde":
        v = crudo.get(k, crudo.get(f"factor_{k}")) if isinstance(crudo, dict) else None
        if v is None:
            v = nivel.get(f"factor_{k}")
        out[k] = _num(v)
    return out


def _criterio_factor(tabla: Dict[float, str], valor: Optional[float]) -> str:
    if valor is None:
        return "No disponible"
    for k, txt in tabla.items():
        if abs(k - valor) < 1e-9:
            return txt
    return "Valor fuera de tabla"


def _margen_lateral(nivel: Dict[str, Any], h: Optional[float]) -> int:
    """H=1 para 11 m ≤ H ≤ 60 m (Fig. B.4); H=3 en el resto (Fig. B.1). Igual que el servicio de cálculo."""
    m = _num(nivel.get("margen_lateral"))
    if m is not None:
        return 1 if int(round(m)) == 1 else 3
    return 1 if h is not None and 11 <= h <= 60 else 3


def _bloque_formula(num: _Numeracion, titulo: str, formula: str, reemplazo: str,
                    resultado: str, unidad: str = "", nota: str = "") -> str:
    """Fórmula → reemplazo de valores → resultado (igual que la pantalla «Nivel de Protección»).
    formula / reemplazo / unidad llegan como HTML ya escapado."""
    filas = [
        [("Fórmula", "k"), (formula, "mono")],
        [("Reemplazo de valores", "k"), (reemplazo, "mono")],
        [("Resultado", "k"), (f"<b>{html.escape(resultado)}</b> {unidad}", "mono")],
    ]
    out = _tabla_rotulada(num, titulo, [("Elemento", "", "30%"), ("Expresión", "", "")], filas)
    if nota:
        out += f'<p class="nota"><i>Nota.</i> {html.escape(nota)}</p>'
    return out


def _seccion_nivel(num: _Numeracion, nivel: Dict[str, Any]) -> str:
    """Sección «Cálculo del nivel de protección»: factores adoptados + Ae, Nd, Nc y criterio F.1."""
    h2 = lambda t: f"<h2>{html.escape(t)}</h2>"  # noqa: E731
    zona = nivel.get("zona_ceraunica") or {}
    fac = _factores_de(nivel)
    l, w, h = (_num(nivel.get(k)) for k in ("longitud_edificacion", "anchura_edificacion", "altura_edificacion"))
    ng, ae = _num(zona.get("ng", nivel.get("densidad_ng"))), _num(nivel.get("ae"))
    nd, nc = _num(nivel.get("nd")), _num(nivel.get("nc"))
    ef = _num(nivel.get("eficiencia_minima"))
    np_calc, np_rec = nivel.get("nivel_proteccion"), nivel.get("nivel_proteccion_recomendado")
    out: List[str] = []

    out.append(
        '<table class="kpi"><tr>'
        f'<td><div class="kl">NIVEL ADOPTADO</div><div class="kv">{_t(NIVEL_LABELS.get(np_calc, np_calc))}</div></td>'
        '<td class="sp"></td>'
        f'<td><div class="kl">NIVEL RECOMENDADO</div><div class="kv">{_t(NIVEL_LABELS.get(np_rec, np_rec))}</div></td>'
        '<td class="sp"></td>'
        f'<td><div class="kl">ESFERA RODANTE</div><div class="kv">R = {_n(nivel.get("radio_esfera"), 0)} m</div></td>'
        '</tr></table>'
    )

    # Datos de partida
    out.append(h2("Datos de partida"))
    zona_txt = ", ".join(str(v) for v in (zona.get("nombre"), zona.get("ciudad")) if v)
    out.append(_tabla_rotulada(
        num, "Datos identificados del proyecto",
        [("Dato", "", "62%"), ("Valor", "r", "")],
        [
            [("Zona ceráunica", ""), (_t(zona_txt), "r")],
            [("Densidad de descargas a tierra (Ng)", ""), (html.escape(_n(ng, 2)), "r mono")],
            [("Longitud de la edificación (L)", ""), (html.escape(_n(l, 2, " m")), "r mono")],
            [("Anchura de la edificación (W)", ""), (html.escape(_n(w, 2, " m")), "r mono")],
            [("Altura de la edificación (H)", ""), (html.escape(_n(h, 2, " m")), "r mono")],
        ],
    ))

    # Factores elegidos (Anexo E)
    out.append(h2("Factores de riesgo adoptados"))
    out.append(_tabla_rotulada(
        num, "Factores de riesgo del Anexo E elegidos para el proyecto",
        [("Factor", "", "22%"), ("Criterio adoptado", "", "22%"), ("Tabla", "c", "10%"), ("Valor", "r", "11%")],
        [[(html.escape(nombre), ""), (html.escape(_criterio_factor(tabla, fac[k])), ""),
          (html.escape(t), "c mono"), (html.escape(_n(fac[k], 1)), "r mono")]
         for k, nombre, t, tabla in FACTORES_ANEXO_E],
    ))
    out.append('<p class="nota"><i>Nota.</i> Tablas E.1 a E.5 (IEC 62305-2 / IRAM 2184 / AEA 92305-11).</p>')

    # Ae
    out.append(h2("Cálculo"))
    m1 = _margen_lateral(nivel, h) == 1
    ln, wn, hn = _n(l, 2), _n(w, 2), _n(h, 2)
    if m1:
        f_ae = "Ae = L·W + 2H·(L+W) + π·H²"
        r_ae = f"Ae = {ln}·{wn} + 2·{hn}·({ln}+{wn}) + π·{hn}²"
        nota_ae = (f"Margen lateral H=1 porque la altura de la estructura (H = {hn} m) está en el rango "
                   "11 m ≤ H ≤ 60 m (Fig. B.4; Anexo G, AEA 92305-11).")
    else:
        f_ae = "Ae = L·W + 6H·(L+W) + 9·π·H²"
        r_ae = f"Ae = {ln}·{wn} + 6·{hn}·({ln}+{wn}) + 9·π·{hn}²"
        nota_ae = (f"Margen lateral H=3 porque la altura de la estructura (H = {hn} m) está en el rango "
                   "2 m ≤ H ≤ 10 m (Fig. B.1; Anexo G, AEA 92305-11).")
    out.append(_bloque_formula(num, "Área colectora equivalente (Ae), Anexo B",
                               html.escape(f_ae), html.escape(r_ae), _n(ae, 2), "m²", nota_ae))

    # Nd
    out.append(_bloque_formula(
        num, "Frecuencia esperable de descargas directas (Nd), Anexo D",
        "Nd = Ng · Ae · 10<sup>−6</sup>", f"Nd = {_n(ng, 2)} · {_n(ae, 2)} · 10<sup>−6</sup>",
        _n(nd, 2), "descargas directas/año"))

    # Nc
    prod = " · ".join(_n(fac[k], 1) for k in "abcde")
    out.append(_bloque_formula(
        num, "Frecuencia aceptable corregida (Nc), Anexo E",
        "Nc = (A · B · C · D · E) · Nd", f"Nc = ({prod}) · {_n(nd, 2)}", _n(nc, 2), "descargas/año"))

    # Criterio F.1
    requiere = (nd > nc) if (nd is not None and nc is not None) else bool(ef)
    filas = [
        [("Nd (impactos directos)", "k"), (html.escape(_n(nd, 2)), "mono")],
        [("Nc (frecuencia aceptable)", "k"), (html.escape(_n(nc, 2)), "mono")],
        [("Condición", "k"), ("Nd &gt; Nc: se requiere SPCR" if requiere
                              else "Nd ≤ Nc: no se exige SPCR obligatorio", "")],
    ]
    if requiere:
        e_val = ef if ef is not None else (1 - nc / nd if nd else None)
        filas.append([("Eficiencia requerida", "k"),
                      (html.escape(f"E = 1 − (Nc/Nd) = 1 − ({_n(nc, 2)}/{_n(nd, 2)}) = {_n(e_val, 2)}"), "mono")])
    filas.append([("Nivel recomendado", "k"), (f"<b>{_t(NIVEL_LABELS.get(np_rec, np_rec))}</b>", "")])
    filas.append([("Nivel adoptado", "k"), (f"<b>{_t(NIVEL_LABELS.get(np_calc, np_calc))}</b>", "")])
    out.append(_tabla_rotulada(num, "Criterio F.1: nivel de protección",
                               [("Elemento", "", "30%"), ("Resultado", "", "")], filas))
    out.append('<p class="nota"><i>Nota.</i> '
               + ("Con E = 1 − (Nc/Nd) se ubica el nivel en la Tabla F.1."
                  if requiere else
                  "Según el inciso F.1 no se exige SPCR; se informa el Nivel IV como referencia mínima.")
               + " Valores guardados en el paso «Nivel de Protección».</p>")
    return "".join(out)


def _construir_cuerpo(datos: Dict[str, Any], imagenes: List[Dict[str, Any]],
                      declaracion: bool) -> Tuple[str, List[Tuple[str, str, str]], _Numeracion]:
    """Devuelve (html, secciones[(id, número, título)], numeración)."""
    num = _Numeracion()
    secciones: List[Tuple[str, str, str]] = []
    img_por_clave = {i["clave"]: i for i in imagenes}

    proyecto = datos.get("proyecto") or {}
    nivel = datos.get("nivel_proteccion") or None
    cobertura = datos.get("cobertura") or None
    materiales = datos.get("materiales") or []
    mastiles = datos.get("mastiles") or []
    ids = datos.get("ids") or {}
    total_mat = datos.get("total_mastiles_materiales") or 0

    partes: List[str] = []

    contador = [0]

    def seccion(sid: str, titulo: str, salto: bool) -> str:
        contador[0] += 1
        numero = str(contador[0])
        secciones.append((sid, numero, titulo))
        cls = ' class="pb"' if salto else ""
        return (f'<div{cls}><div class="kicker">SECCIÓN {numero}</div>'
                f'<h1 id="{sid}">{html.escape(titulo)}</h1></div>')

    # ── 1. Nivel de protección (los datos del proyecto van en la portada) ────
    partes.append(seccion("sec2", "Cálculo del nivel de protección", salto=False))
    if not nivel:
        partes.append('<p class="nd">No se encontró un cálculo de nivel de protección para este proyecto.</p>')
    else:
        partes.append(_seccion_nivel(num, nivel))

    # ── 3. Plano 2D ──────────────────────────────────────────────────────────
    partes.append(seccion("sec3", "Plano base 2D con mástiles", salto=True))
    partes.append(
        f'<p class="lead">Plano con la geometría validada y {len(mastiles)} mástiles captores ubicados '
        f'(Modelo 2D ID: {_t(ids.get("id_modelo2d"))}).</p>'
    )
    if "plano" in img_por_clave:
        partes.append(_bloque_imagen(
            num, img_por_clave["plano"],
            "Cada pin numerado identifica un mástil captor; la etiqueta indica su altura. "
            "Las cotas corresponden a los niveles de las cubiertas."))
    else:
        partes.append('<p class="nd">El plano 2D no fue incluido en este documento.</p>')

    # ── 4. Vistas 3D ─────────────────────────────────────────────────────────
    partes.append(seccion("sec4", "Vistas del modelo 3D con cobertura SPDA", salto=False))
    partes.append(
        f'<p class="lead">Vistas del modelo 3D con los mástiles y la cobertura de los pararrayos '
        f'(Modelo 3D ID: {_t(ids.get("id_modelo3d"))}).</p>'
    )
    vistas = [img_por_clave[k] for k in ORDEN_IMAGENES if k != "plano" and k in img_por_clave]
    if not vistas:
        partes.append('<p class="nd">No se seleccionaron vistas 3D para este documento.</p>')
    for img in vistas:
        partes.append(_bloque_imagen(num, img, NOTAS_VISTA.get(img["clave"], "")))

    # ── 5. Cobertura ─────────────────────────────────────────────────────────
    partes.append(seccion("sec5", "Detalle de cobertura SPDA", salto=False))
    if not cobertura:
        partes.append('<p class="nd">Sin datos de cobertura. Confirme la ubicación de mástiles en el paso 5.</p>')
    else:
        prismas = cobertura.get("prismas") or []
        zonas = cobertura.get("zonas_desprotegidas") or []
        area_desp = sum((_num(z.get("area_m2", z.get("area"))) or 0.0) for z in zonas)
        n_prot = sum(1 for p in prismas if p.get("estado") == "protegido")
        n_parc = sum(1 for p in prismas if p.get("estado") == "parcial")
        n_desp = sum(1 for p in prismas if p.get("estado") == "desprotegido")
        partes.append(
            f'<p class="lead">Cobertura calculada con el método de la esfera rodante '
            f'(R = {_n(cobertura.get("radio_esfera_rodante_r"), 0)} m) para '
            f'{_n(cobertura.get("total_mastiles"), 0)} mástiles.</p>'
        )
        filas = [
            ("Cobertura SPDA", _pct(cobertura.get("porcentaje_cobertura"))),
            ("Radio de esfera rodante (R)", _n(cobertura.get("radio_esfera_rodante_r"), 0, " m")),
            ("Total de mástiles", _n(cobertura.get("total_mastiles"), 0)),
            ("Área total de cubiertas", _n(cobertura.get("area_total_m2"), 2, " m²")),
            ("Área de cubierta protegida", _n(cobertura.get("area_protegida_m2"), 2, " m²")),
            ("Zonas desprotegidas", _n(len(zonas), 0)),
        ]
        if area_desp > 0:
            filas.append(("Área de las zonas desprotegidas", _n(area_desp, 2, " m²")))
        filas += [
            ("Cubiertas (total)", _n(len(prismas), 0)),
            ("Cubiertas protegidas", _n(n_prot, 0)),
            ("Cubiertas parciales", _n(n_parc, 0)),
            ("Cubiertas desprotegidas", _n(n_desp, 0)),
        ]
        partes.append(_tabla_rotulada(
            num, "Resumen de la cobertura SPDA",
            [("Indicador", "", "62%"), ("Valor", "r", "")],
            [[(html.escape(k), ""), (html.escape(v), "r mono")] for k, v in filas],
        ))
        partes.append('<p class="nota"><i>Nota.</i> Resultados del cálculo de cobertura del paso «Ubicación de Mástiles».</p>')

        for adv in cobertura.get("advertencias") or []:
            partes.append(f'<p class="aviso"><b>Atención.</b> {html.escape(str(adv))}</p>')

        if prismas:
            filas_c = []
            for p in prismas:
                etiqueta, color = ESTADO_CUBIERTA.get(p.get("estado"), (str(p.get("estado") or "—"), MUTED))
                filas_c.append([
                    (html.escape(str(p.get("id", "—"))), "mono"),
                    (f'<span style="color:{color}">{html.escape(etiqueta)}</span>', ""),
                    (html.escape(_pct(p.get("porcentaje_cobertura"), 1)), "r mono"),
                ])
            if len(filas_c) > 12:
                # Muchas cubiertas: dos bloques lado a lado (la tabla ocupa la mitad del alto).
                mitad = (len(filas_c) + 1) // 2
                izq, der = filas_c[:mitad], filas_c[mitad:]
                vacia = [("", ""), ("", ""), ("", "")]
                filas_2 = [izq[i] + [("", "")] + (der[i] if i < len(der) else vacia) for i in range(mitad)]
                bloque = [("Cubierta", "", "15%"), ("Estado", "", "16%"), ("Cobertura", "r", "15%")]
                partes.append(_tabla_rotulada(
                    num, "Cobertura por cubierta", bloque + [("", "", "8%")] + bloque, filas_2))
            else:
                partes.append(_tabla_rotulada(
                    num, "Cobertura por cubierta",
                    [("Cubierta", "", "40%"), ("Estado", "", "30%"), ("Cobertura", "r", "")], filas_c))
            partes.append('<p class="nota"><i>Nota.</i> Protegido: la cubierta está cubierta por la esfera rodante; '
                          'desprotegido: sin cobertura; parcial: cobertura incompleta.</p>')

        ternas = cobertura.get("triangulos_sin_esfera") or []
        if ternas:
            partes.append(
                f'<p class="aviso"><b>Ternas sin esfera posible: {len(ternas)}.</b> Existen {len(ternas)} terna(s) '
                'de mástiles en las que la esfera rodante no puede ser tangente a los tres sin tocar la cubierta. '
                'Revise las alturas y separaciones en el paso 5.</p>')
        elif prismas:
            partes.append('<p class="ok">Todas las ternas admiten esfera rodante.</p>')

    # ── 6. Materiales ────────────────────────────────────────────────────────
    partes.append(seccion("sec6", "Listado de materiales", salto=False))
    if not materiales:
        partes.append('<p class="nd">Sin materiales: el proyecto no tiene mástiles colocados.</p>')
    else:
        extra = ""
        if ids.get("id_modelo2d") and mastiles and len(mastiles) != total_mat:
            extra = (f" Nota: el modelo 2D activo tiene {len(mastiles)} mástil(es); el listado incluye "
                     "todos los del proyecto.")
        partes.append(f'<p class="lead">Cómputo métrico según {total_mat} mástil(es) del proyecto '
                      f'(todos los modelos 2D).{html.escape(extra)}</p>')
        partes.append(_tabla_rotulada(
            num, "Listado de materiales del sistema de captación",
            [("Código", "", "18%"), ("Descripción", "", ""), ("Cantidad", "r", "14%")],
            [[(_t(m.get("codigo"), "—"), "mono"), (_t(m.get("descripcion")), ""),
              (html.escape(str(m.get("cantidad", "—"))), "r mono")] for m in materiales],
        ))
        partes.append('<p class="nota"><i>Nota.</i> Los códigos provienen del catálogo de materiales; «—» indica código no asignado.</p>')

    # ── 7. Declaración ───────────────────────────────────────────────────────
    if declaracion:
        partes.append(seccion("sec7", "Declaración de cumplimiento", salto=False))
        partes.append(
            '<p class="decl">El calculo de este informe se realizo conforme a las normativas de seguridad laboral '
            'vigentes (Ley 19.587, Decreto 351/79 Anexo VI e IRAM 2184).</p>')
        partes.append(
            '<table class="firma" style="width:100%"><tr>'
            '<td class="l" style="width:46%">Firma y aclaración del profesional</td><td style="width:8%"></td>'
            f'<td class="l" style="width:46%">{_t(proyecto.get("proyectista"), "Proyectista")} · Matrícula N.º</td>'
            '</tr></table>')

    return f"<body>{''.join(partes)}</body>", secciones, num


def _renderizar_cuerpo(html_doc: str, imagenes: List[Dict[str, Any]]) -> Tuple["fitz.Document", Dict[str, int]]:
    """Maqueta el HTML en páginas A4. Devuelve (documento, {id_elemento: n.º de página 0-based})."""
    archivo = fitz.Archive(str(FONTS_DIR))
    for img in imagenes:
        archivo.add(img["bytes"], f'img_{img["clave"]}.{img["ext"]}')

    story = fitz.Story(html=html_doc, user_css=CSS, archive=archivo)
    buf = io.BytesIO()
    writer = fitz.DocumentWriter(buf)
    zona = fitz.Rect(MARGEN_IZQ, MARGEN_SUP, A4.width - MARGEN_DER, A4.height - MARGEN_INF)

    paginas_por_id: Dict[str, int] = {}
    actual = [0]

    def registrar(pos: Any) -> None:
        if pos.open_close & 1 and pos.id and pos.id not in paginas_por_id:
            paginas_por_id[pos.id] = actual[0]

    mas = 1
    pno = 0
    while mas:
        if pno >= MAX_PAGINAS_CUERPO:
            raise RuntimeError("La memoria superó el máximo de páginas permitido.")
        actual[0] = pno
        dev = writer.begin_page(A4)
        mas, _ = story.place(zona)
        story.element_positions(registrar, {})
        story.draw(dev)
        writer.end_page()
        pno += 1
    writer.close()
    return fitz.open("pdf", buf.getvalue()), paginas_por_id


# ──────────────────────────────────────────────────────────────────────────────
# Portada, encabezado y pie
# ──────────────────────────────────────────────────────────────────────────────

def _imagen_principal(imagenes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    por = {i["clave"]: i for i in imagenes}
    for k in ["iso", "iso_der", "caballera", "militar", "front", "side", "top", "plano"]:
        if k in por:
            return por[k]
    return None


def _portada(page: "fitz.Page", fuentes: _Fuentes, datos: Dict[str, Any],
             imagenes: List[Dict[str, Any]]) -> None:
    proyecto = datos.get("proyecto") or {}
    x0, x1 = MARGEN_IZQ, A4.width - MARGEN_DER

    # Cabecera: datos a la izquierda, logo a la derecha
    _dibujar(page, x0, 52, "PROYECTO N.º " + str(proyecto.get("id_proyecto") or "—"),
             fuentes.sans_semi, 7.2, MUTED, tracking=0.5)
    _dibujar(page, x0, 64, datetime.now().strftime("%d/%m/%Y"), fuentes.sans, 7.6, MUTED)
    _dibujar_logo(page, fuentes, x1, 38, 26, derecha=True)
    _linea(page, x0, 82, x1, 82, RULE, 0.6)

    # Imagen principal (como la portada de un informe técnico)
    caja = fitz.Rect(x0, 98, x1, 288)
    principal = _imagen_principal(imagenes)
    if principal:
        page.draw_rect(caja, color=_rgb(RULE), fill=_rgb("#F7F9FC"), width=0.6)
        page.insert_image(caja + (6, 6, -6, -6), stream=principal["bytes"], keep_proportion=True)
    else:
        page.draw_rect(caja, color=None, fill=_rgb("#0F2742"))
        _dibujar_logo(page, fuentes, caja.x0 + 28, caja.y1 - 28 - 40, 40)

    # Títulos
    y = 318
    _dibujar(page, x0, y, "MEMORIA DESCRIPTIVA", fuentes.cond_semi, 10.5, BRAND, tracking=1.6)
    y += 30
    for linea in _envolver(fuentes.cond_bold, "Sistema de Protección contra Descargas Atmosféricas (SPDA)", 24, ANCHO_UTIL):
        _dibujar(page, x0, y, linea, fuentes.cond_bold, 24, INK)
        y += 27
    y += 4
    nombre = str(proyecto.get("nombre") or "Proyecto sin nombre")
    for linea in _envolver(fuentes.sans_med, nombre, 13, ANCHO_UTIL)[:2]:
        _dibujar(page, x0, y, linea, fuentes.sans_med, 13, INK)
        y += 18
    _dibujar(page, x0, y + 2, "Ley 19.587 · Decreto 351/79 · IRAM 2184", fuentes.sans, 8.5, MUTED)

    # Datos del proyecto (tabla de rótulo / valor, estilo APA: filete grueso arriba y abajo)
    # y += 34
    # _dibujar(page, x0, y, "DATOS DEL PROYECTO", fuentes.cond_semi, 9, BRAND, tracking=1.4)
    # y += 7
    # _linea(page, x0, y, x1, y, INK, 1.2)
    # ubic = ", ".join(str(v) for v in (proyecto.get("ubicacion"), proyecto.get("localidad"),
    #                                  proyecto.get("provincia")) if v)
    # filas = [
    #     ("Nombre del proyecto", proyecto.get("nombre")),
    #     ("Cliente", proyecto.get("cliente")),
    #     ("Proyectista", proyecto.get("proyectista")),
    #     ("Estado", proyecto.get("estado")),
    #     ("Ubicación", proyecto.get("ubicacion")),
    #     ("Localidad", proyecto.get("localidad")),
    #     ("Departamento", proyecto.get("departamento")),
    #     ("Provincia", proyecto.get("provincia")),
    #     ("Fecha del proyecto", _fecha(proyecto.get("fecha_del_proyecto"))),
    #     ("Fecha de creación", _fecha(proyecto.get("fecha_creacion"))),
    # ]
    # if proyecto.get("descripcion"):
    #     filas.append(("Descripción", proyecto.get("descripcion")))
    # xv = x0 + 130
    # for i, (rotulo, valor) in enumerate(filas):
    #     texto = str(valor).strip() if valor is not None and str(valor).strip() else "No disponible"
    #     lineas = _envolver(fuentes.sans_med, texto, 9, x1 - xv - 4)[:3]
    #     y += 14
    #     _dibujar(page, x0 + 2, y, rotulo, fuentes.sans, 8.2, MUTED)
    #     for j, linea in enumerate(lineas):
    #         _dibujar(page, xv, y + j * 11.5, linea, fuentes.sans_med, 9, INK)
    #     y += (len(lineas) - 1) * 11.5 + 4
    #     if i < len(filas) - 1:
    #         _linea(page, x0, y, x1, y, RULE, 0.4)
    # _linea(page, x0, y, x1, y, INK, 1.2)
    # _dibujar(page, x0, y + 12, "«No disponible» indica que el dato no está cargado en el proyecto.",
    #          fuentes.sans, 7, MUTED)
    # Bloque inferior: cliente, ubicación, proyectista y fechas
    base = 490
    _linea(page, x0, base - 22, x1, base - 22, RULE, 0.6)
    ubic = ", ".join(str(v) for v in (proyecto.get("ubicacion"), proyecto.get("localidad"),
                                     proyecto.get("provincia")) if v)
    celdas = [
        ("CLIENTE", proyecto.get("cliente")),
        ("PROYECTISTA", proyecto.get("proyectista")),
        ("UBICACIÓN", ubic or None),
        ("UBICACION", proyecto.get("ubicacion")),
        ("LOCALIDAD", proyecto.get("localidad")),
        ("DEPARTAMENTO", proyecto.get("departamento")),
        ("PROVINCIA", proyecto.get("provincia")),
        ("FECHA DEL PROYECTO", _fecha(proyecto.get("fecha_del_proyecto") or proyecto.get("fecha_creacion"))),
        #("FECHA DE CREACION", _fecha(proyecto.get("fecha_creacion"))),
    ]
    col_w = ANCHO_UTIL / 2
    for i, (rotulo, valor) in enumerate(celdas):
        cx = x0 + (i % 2) * col_w
        cy = base + (i // 2) * 46
        _dibujar(page, cx, cy, rotulo, fuentes.sans_semi, 6.8, MUTED, tracking=0.6)
        texto = str(valor) if valor and str(valor).strip() else "No disponible"
        for j, linea in enumerate(_envolver(fuentes.sans_med, texto, 10, col_w - 18)[:2]):
            _dibujar(page, cx, cy + 14 + j * 12.5, linea, fuentes.sans_med, 10, INK)

    # Texto vertical a la derecha (como en los informes de DIALux)
    pivote = fitz.Point(A4.width - 30, A4.height - 44)
    _dibujar(page, pivote.x, pivote.y, "Generado con FARADYNE", fuentes.sans, 7, MUTED,
             morph=(pivote, fitz.Matrix(90)))


def _encabezado_y_pie(doc: "fitz.Document", fuentes: _Fuentes, datos: Dict[str, Any]) -> None:
    proyecto = datos.get("proyecto") or {}
    x0, x1 = MARGEN_IZQ, A4.width - MARGEN_DER
    total = doc.page_count
    nombre = str(proyecto.get("nombre") or "Proyecto")
    for i in range(1, total):          # la portada (página 1) no lleva encabezado ni pie
        page = doc[i]
        # Las páginas que salen del Story terminan con un estado gráfico sin balancear (q/Q);
        # sin esto, el texto que se agrega después sale espejado y al pie de la página.
        page.wrap_contents()
        _dibujar(page, x0, 38, "MEMORIA DESCRIPTIVA", fuentes.sans_semi, 6.8, BRAND, tracking=0.8)
        _dibujar(page, x0, 50, f"{nombre} · Proyecto N.º {proyecto.get('id_proyecto', '—')}",
                 fuentes.sans, 8, MUTED)
        _dibujar_logo(page, fuentes, x1, 30, 18, derecha=True)
        _linea(page, x0, 62, x1, 62, RULE, 0.6)

        _linea(page, x0, A4.height - 46, x1, A4.height - 46, RULE, 0.6)
        _dibujar(page, x0, A4.height - 32, "FARADYNE · Sistema de Protección contra Descargas Atmosféricas",
                 fuentes.sans, 7, MUTED)
        _dibujar(page, x1, A4.height - 32, f"{i + 1} / {total}", fuentes.mono, 7.5, INK, derecha=True)


# ──────────────────────────────────────────────────────────────────────────────
# API pública
# ──────────────────────────────────────────────────────────────────────────────

def generar_memoria_pdf(ruta: Path, datos: Dict[str, Any], imagenes: List[Dict[str, Any]],
                        declaracion: bool = True) -> Path:
    """Arma y guarda el PDF en `ruta`.

    datos: la misma estructura que devuelve el endpoint de vista previa
           (proyecto, nivel_proteccion, cobertura, mastiles, materiales,
           total_mastiles_materiales, ids).
    imagenes: salida de decodificar_imagenes() (puede estar vacía).
    """
    for req in ("IBMPlexSans-Regular.ttf", "IBMPlexSansCondensed-Bold.ttf", "IBMPlexMono-Regular.ttf"):
        if not (FONTS_DIR / req).is_file():
            raise FileNotFoundError(f"Falta la fuente {req} en {FONTS_DIR}")

    fuentes = _Fuentes()
    html_doc, secciones, num = _construir_cuerpo(datos, imagenes, declaracion)
    cuerpo, pag = _renderizar_cuerpo(html_doc, imagenes)

    OFFSET = 2  # la portada es la página 1: el cuerpo arranca en la página 2
    doc = fitz.open()
    doc.new_page(width=A4.width, height=A4.height)  # portada (con los datos del proyecto)
    doc.insert_pdf(cuerpo)
    cuerpo.close()

    # Se vuelve a pedir la página: insert_pdf invalida los objetos Page anteriores.
    _portada(doc[0], fuentes, datos, imagenes)
    _encabezado_y_pie(doc, fuentes, datos)

    toc = [[1, "Portada", 1]]
    toc += [[1, f"{n}. {titulo}", pag.get(sid, 0) + OFFSET] for sid, n, titulo in secciones]
    doc.set_toc(toc)

    proyecto = datos.get("proyecto") or {}
    doc.set_metadata({
        "title": f"Memoria descriptiva — {proyecto.get('nombre') or 'Proyecto'}",
        "author": str(proyecto.get("proyectista") or "FARADYNE"),
        "subject": "Sistema de Protección contra Descargas Atmosféricas (SPDA)",
        "creator": "FARADYNE",
        "producer": "FARADYNE",
    })

    try:
        doc.subset_fonts()  # reduce el peso; necesita fontTools (ya está en requirements.txt)
    except Exception:
        pass

    ruta.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(ruta), garbage=3, deflate=True)
    doc.close()
    return ruta
