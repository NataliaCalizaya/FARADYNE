from __future__ import annotations

import functools
import threading
import uuid
from typing import Any, Dict, List, Optional, Tuple

from shapely.geometry import Polygon, box

from app.repositories.plano_repository import PlanoRepository
from app.services.niveles_utils import NivelesUtils


# ---------------------------------------------------------------------
# Bloqueo por Modelo 2D
#
# Cada operación del editor hace "leer modelo -> modificar -> guardar". Si
# llegan dos pedidos a la vez sobre el mismo modelo (por ejemplo dos
# triángulos creados casi en el mismo instante), los dos leen el modelo sin
# el polígono del otro y el último en guardar pisa al primero: el polígono
# perdido queda "fantasma" en el visor y luego no se puede eliminar.
# ---------------------------------------------------------------------
_LOCKS_MODELO: Dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def _con_lock_modelo(func):
    @functools.wraps(func)
    def wrapper(cls, id_modelo2d, *args, **kwargs):
        with _LOCKS_GUARD:
            lock = _LOCKS_MODELO.setdefault(str(id_modelo2d), threading.RLock())

        with lock:
            return func(cls, id_modelo2d, *args, **kwargs)

    return wrapper


class EditorModelo2DService:
    """
    Servicio encargado de editar manualmente un Modelo2D luego de su
    interpretación automática.

    IMPORTANTE:
        Este servicio NO interpreta nuevamente el PDF.

    El PDFInterpreterService detecta capas, polígonos y niveles. Este servicio
    solamente permite:
        - crear / actualizar / eliminar rectángulos y triángulos
        - crear / actualizar / eliminar niveles (punto elegido en el visor)
        - asociar un nivel a un LADO de un polígono
        - desasociar un nivel de un polígono (también los reconocidos)
        - validar el Modelo2D

    Fuente de verdad de las asociaciones: modelo["cotas_altura"][i]
    ["asociaciones"] (ver niveles_utils.py). Las copias que cada polígono
    guarda en "niveles", nivel_bajo/medio/alto, tipo_cubierta y pendiente se
    regeneran en cada guardado; nunca se editan a mano.
    """

    # =========================================================
    # ACCESO AL MODELO
    # =========================================================

    @staticmethod
    def _get_modelo2d(id_modelo2d: str) -> Dict[str, Any]:
        modelo = PlanoRepository.get_modelo2d_by_id(id_modelo2d)

        if not modelo:
            raise ValueError(
                f"No se encontró el Modelo 2D con ID '{id_modelo2d}'."
            )

        return modelo

    @staticmethod
    def _get_list(modelo: Dict[str, Any], field: str) -> List[Any]:
        value = modelo.get(field)

        if value is None:
            return []

        if not isinstance(value, list):
            raise ValueError(
                f"El campo '{field}' del Modelo 2D no tiene un formato válido."
            )

        return value

    @classmethod
    def _cargar(
        cls, id_modelo2d: str
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Carga el modelo. Si es de antes de las asociaciones por lado, lo
        migra en memoria (se persiste en el primer guardado).
        """
        modelo = cls._get_modelo2d(id_modelo2d)
        poligonos = cls._get_list(modelo, "poligonos")
        niveles = cls._get_list(modelo, "cotas_altura")

        NivelesUtils.migrar_formato_anterior(poligonos, niveles)

        return modelo, poligonos, niveles

    @classmethod
    def _guardar(
        cls,
        id_modelo2d: str,
        modelo: Dict[str, Any],
        poligonos: List[Dict[str, Any]],
        niveles: List[Dict[str, Any]],
        **extra: Any,
    ) -> Optional[Dict[str, Any]]:
        """Regenera los derivados de los polígonos y persiste."""
        NivelesUtils.reconstruir_niveles_poligonos(poligonos, niveles)

        modelo["poligonos"] = poligonos
        modelo["cotas_altura"] = niveles
        modelo.update(extra)

        return PlanoRepository.update_modelo2d(
            id_modelo2d=id_modelo2d,
            poligonos=poligonos,
            cotas_altura=niveles,
            **extra,
        )

    @staticmethod
    def _buscar(
        items: List[Dict[str, Any]], item_id: str, etiqueta: str
    ) -> Dict[str, Any]:
        encontrado = next(
            (i for i in items if str(i.get("id")) == str(item_id)), None
        )

        if encontrado is None:
            raise ValueError(f"No se encontró el {etiqueta} '{item_id}'.")

        return encontrado

    # =========================================================
    # CAPAS
    # =========================================================
    # "capas" puede venir como lista de str (lo que genera el intérprete) o
    # de dict {"nombre", ...}. Se aceptan las dos y se respeta el formato.

    @staticmethod
    def _nombre_capa(capa: Any) -> str:
        if isinstance(capa, dict):
            return str(capa.get("nombre") or capa.get("name") or "").strip()

        return str(capa or "").strip()

    @classmethod
    def _buscar_capa(cls, modelo: Dict[str, Any], capa: Optional[str]) -> Optional[str]:
        objetivo = str(capa or "").strip().upper()

        for item in modelo.get("capas") or []:
            nombre = cls._nombre_capa(item)

            if nombre and nombre.upper() == objetivo:
                return nombre

        return None

    @classmethod
    def _validate_existing_layer(
        cls, modelo: Dict[str, Any], capa: Optional[str]
    ) -> str:
        if not (modelo.get("capas") or []):
            raise ValueError("El Modelo 2D no contiene capas reconocidas.")

        if not capa:
            raise ValueError("Debe seleccionarse una capa existente.")

        existente = cls._buscar_capa(modelo, capa)

        if existente is None:
            raise ValueError(
                f"La capa '{str(capa).strip()}' no existe en el Modelo 2D."
            )

        return existente

    @classmethod
    def _capa_para_nivel(
        cls, modelo: Dict[str, Any], capa: Optional[str]
    ) -> str:
        """
        Capa de un nivel manual: la pedida, o la que usan los niveles ya
        existentes, o "LEVELS". Si no existe en el modelo se crea.
        """
        nombre = (capa or "").strip()

        if not nombre:
            for nivel in modelo.get("cotas_altura") or []:
                if nivel.get("capa"):
                    nombre = str(nivel["capa"])
                    break

        nombre = nombre or "LEVELS"
        existente = cls._buscar_capa(modelo, nombre)

        if existente:
            return existente

        capas = modelo.get("capas")
        capas = capas if isinstance(capas, list) else []

        if any(isinstance(c, dict) for c in capas):
            capas.append({"nombre": nombre, "color": "#FFFFFF", "visible": True})
        else:
            capas.append(nombre)

        modelo["capas"] = capas
        return nombre

    # =========================================================
    # PUNTOS
    # =========================================================

    @staticmethod
    def _normalize_point(punto: Any) -> Dict[str, float]:
        if isinstance(punto, (list, tuple)):
            if len(punto) != 2:
                raise ValueError("Un punto debe tener exactamente 2 coordenadas.")

            return {"x": float(punto[0]), "y": float(punto[1])}

        if isinstance(punto, dict):
            if "x" not in punto or "y" not in punto:
                raise ValueError("El punto debe contener x e y.")

            return {"x": float(punto["x"]), "y": float(punto["y"])}

        raise ValueError("Formato de punto no válido.")

    @classmethod
    def _normalize_points(cls, puntos: List[Any]) -> List[Dict[str, float]]:
        if not isinstance(puntos, list):
            raise ValueError("Los puntos deben ser una lista.")

        return [cls._normalize_point(p) for p in puntos]

    @staticmethod
    def _normalize_selected_point(punto: Dict[str, Any]) -> Dict[str, float]:
        """
        Punto elegido en el GeometryViewer. El usuario NO escribe las
        coordenadas: llegan de la selección en el visor.
        """
        if not isinstance(punto, dict):
            raise ValueError("El punto seleccionado debe ser un objeto.")

        if "x" not in punto or "y" not in punto:
            raise ValueError("El punto seleccionado debe contener 'x' e 'y'.")

        try:
            return {"x": float(punto["x"]), "y": float(punto["y"])}
        except (TypeError, ValueError):
            raise ValueError(
                "Las coordenadas del punto seleccionado deben ser numéricas."
            )

    @staticmethod
    def _validate_polygon_points(
        puntos: List[Dict[str, Any]], cantidad_minima: int = 3
    ) -> List[Dict[str, float]]:
        if not isinstance(puntos, list):
            raise ValueError("Los puntos deben ser una lista.")

        if len(puntos) < cantidad_minima:
            raise ValueError(
                f"La geometría debe tener al menos {cantidad_minima} puntos."
            )

        resultado = []

        for punto in puntos:
            if not isinstance(punto, dict):
                raise ValueError("Cada punto debe tener formato {x, y}.")

            if "x" not in punto or "y" not in punto:
                raise ValueError("Cada punto debe contener x e y.")

            resultado.append({"x": float(punto["x"]), "y": float(punto["y"])})

        return resultado

    # =========================================================
    # POLÍGONOS
    # =========================================================

    @staticmethod
    def _nuevo_poligono(
        tipo: str,
        puntos: List[Dict[str, float]],
        capa: str,
        page: int,
        tipo_cubierta: str,
    ) -> Dict[str, Any]:
        geometry = Polygon([(p["x"], p["y"]) for p in puntos])

        if geometry.is_empty:
            raise ValueError("La superficie generada está vacía.")

        if not geometry.is_valid:
            raise ValueError("Los puntos no forman una superficie válida.")

        if geometry.area <= 1e-9:
            raise ValueError("La superficie no puede tener área cero.")

        min_x, min_y, max_x, max_y = geometry.bounds
        centro = geometry.centroid

        return {
            "id": f"surface_{uuid.uuid4().hex[:12]}",
            "tipo": tipo,
            "capa": capa,
            "page": int(page),
            "puntos": puntos,
            "area": float(geometry.area),
            "bounding_box": {
                "min_x": float(min_x),
                "min_y": float(min_y),
                "max_x": float(max_x),
                "max_y": float(max_y),
            },
            "centro": {"x": float(centro.x), "y": float(centro.y)},
            "niveles": [],
            "nivel_bajo": None,
            "nivel_medio": None,
            "nivel_alto": None,
            "pendiente": None,
            "tipo_cubierta": tipo_cubierta,
            "origen": "manual",
        }

    @classmethod
    @_con_lock_modelo
    def crear_rectangulo(
        cls,
        id_modelo2d: str,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        capa: str,
        page: int = 0,
        tipo_cubierta: str = "pendiente_por_resolver",
    ) -> Dict[str, Any]:
        modelo, poligonos, niveles = cls._cargar(id_modelo2d)
        capa = cls._validate_existing_layer(modelo, capa)

        try:
            x_min, x_max = sorted((float(x1), float(x2)))
            y_min, y_max = sorted((float(y1), float(y2)))
        except (TypeError, ValueError):
            raise ValueError("Las coordenadas del rectángulo deben ser numéricas.")

        if x_min == x_max:
            raise ValueError("El rectángulo no puede tener ancho cero.")

        if y_min == y_max:
            raise ValueError("El rectángulo no puede tener alto cero.")

        poligono = cls._nuevo_poligono(
            "rectangulo",
            [
                {"x": x_min, "y": y_min},
                {"x": x_max, "y": y_min},
                {"x": x_max, "y": y_max},
                {"x": x_min, "y": y_max},
            ],
            capa,
            page,
            tipo_cubierta,
        )

        poligonos.append(poligono)
        cls._guardar(id_modelo2d, modelo, poligonos, niveles)

        return poligono

    @classmethod
    @_con_lock_modelo
    def crear_triangulo(
        cls,
        id_modelo2d: str,
        puntos: List[Any],
        capa: str,
        page: int = 0,
        tipo_cubierta: str = "pendiente_por_resolver",
    ) -> Dict[str, Any]:
        # Antes estaba anidado (con sangría de más) dentro de
        # _create_fitz_rect, después de un return: no existía como método.
        modelo, poligonos, niveles = cls._cargar(id_modelo2d)

        puntos_normalizados = cls._normalize_points(puntos)

        if len(puntos_normalizados) != 3:
            raise ValueError("Un triángulo debe tener exactamente 3 puntos.")

        capa = cls._validate_existing_layer(modelo, capa)

        poligono = cls._nuevo_poligono(
            "triangulo", puntos_normalizados, capa, page, tipo_cubierta
        )

        poligonos.append(poligono)
        cls._guardar(id_modelo2d, modelo, poligonos, niveles)

        return poligono

    @classmethod
    @_con_lock_modelo
    def actualizar_poligono(
        cls,
        id_modelo2d: str,
        id_poligono: str,
        datos: Dict[str, Any],
    ) -> Dict[str, Any]:
        modelo, poligonos, niveles = cls._cargar(id_modelo2d)
        polygon = cls._buscar(poligonos, id_poligono, "polígono")

        if "puntos" in datos:
            puntos = cls._validate_polygon_points(datos["puntos"])
            cantidad_anterior = len(polygon.get("puntos") or [])

            cls._aplicar_puntos(polygon, puntos, id_poligono)

            # Mover un vértice NO cambia los lados: los niveles conservan el
            # suyo. Solo si cambia la cantidad de puntos los índices dejan de
            # valer y cada nivel busca de nuevo su lado más cercano al guardar.
            if len(puntos) != cantidad_anterior:
                cls._remapear_lados(
                    niveles, id_poligono, lambda nivel, lado: None
                )

        if "capa" in datos:
            polygon["capa"] = cls._validate_existing_layer(modelo, datos["capa"])

        if "page" in datos:
            polygon["page"] = int(datos["page"])

        if "tipo" in datos:
            polygon["tipo"] = datos["tipo"]

        if "tipo_cubierta" in datos:
            polygon["tipo_cubierta"] = datos["tipo_cubierta"]

        polygon["origen"] = polygon.get("origen", "manual")

        if not cls._guardar(id_modelo2d, modelo, poligonos, niveles):
            raise ValueError("No se pudo guardar el polígono actualizado.")

        return polygon

    @classmethod
    @_con_lock_modelo
    def eliminar_poligono(
        cls, id_modelo2d: str, id_poligono: str
    ) -> Dict[str, Any]:
        modelo, poligonos, niveles = cls._cargar(id_modelo2d)
        cls._buscar(poligonos, id_poligono, "polígono")

        poligonos = [p for p in poligonos if str(p.get("id")) != str(id_poligono)]

        # Los niveles asociados a ese polígono NO se borran: quedan sin
        # asociar (la asociación huérfana se limpia en _guardar).
        return cls._guardar(id_modelo2d, modelo, poligonos, niveles) or modelo

    # =========================================================
    # VÉRTICES
    # =========================================================

    @staticmethod
    def _aplicar_puntos(
        polygon: Dict[str, Any],
        puntos: List[Dict[str, float]],
        id_poligono: str,
    ) -> None:
        """Valida los puntos y actualiza puntos, area, bounding_box y centro."""
        geometry = Polygon([(p["x"], p["y"]) for p in puntos])

        if not geometry.is_valid:
            geometry = geometry.buffer(0)

        if geometry.is_empty or geometry.area <= 1e-9:
            raise ValueError(
                f"El polígono '{id_poligono}' tiene una geometría inválida."
            )

        min_x, min_y, max_x, max_y = geometry.bounds
        centro = geometry.centroid

        polygon["puntos"] = puntos
        polygon["area"] = float(geometry.area)
        polygon["bounding_box"] = {
            "min_x": float(min_x),
            "min_y": float(min_y),
            "max_x": float(max_x),
            "max_y": float(max_y),
        }
        polygon["centro"] = {"x": float(centro.x), "y": float(centro.y)}

    @staticmethod
    def _remapear_lados(
        niveles: List[Dict[str, Any]],
        id_poligono: str,
        nuevo_lado,
    ) -> None:
        """
        Recalcula el lado de las asociaciones a `id_poligono`.
        nuevo_lado(nivel, lado_actual) -> lado nuevo, o None para que el lado
        se vuelva a buscar (el más cercano) al guardar.
        """
        for nivel in niveles:
            for asociacion in nivel.get("asociaciones") or []:
                if str(asociacion.get("id_poligono")) != str(id_poligono):
                    continue

                try:
                    actual = int(asociacion.get("lado"))
                except (TypeError, ValueError):
                    asociacion["lado"] = None
                    continue

                asociacion["lado"] = nuevo_lado(nivel, actual)

    @staticmethod
    def _ajustar_tipo(polygon: Dict[str, Any]) -> None:
        """Un triángulo con 4 vértices o un rectángulo con 5 pasan a 'poligono'."""
        cantidad = len(polygon.get("puntos") or [])
        tipo = polygon.get("tipo")

        if (tipo == "triangulo" and cantidad != 3) or (
            tipo == "rectangulo" and cantidad != 4
        ):
            polygon["tipo"] = "poligono"

    @classmethod
    @_con_lock_modelo
    def agregar_vertice_poligono(
        cls,
        id_modelo2d: str,
        id_poligono: str,
        punto: Dict[str, Any],
        indice: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Inserta un vértice en el polígono (triángulo, rectángulo o cualquier
        otro: todos son polígonos).

        Sin `indice`, el vértice va sobre el lado más cercano a `punto` y se
        proyecta sobre ese lado, así la forma no cambia hasta que el usuario
        lo arrastre. Con `indice` (1..n) queda entre puntos[indice - 1] y
        puntos[indice % n].

        El lado donde se inserta se parte en dos. Los niveles asociados a ese
        lado quedan en la mitad más cercana y los lados siguientes se corren
        un lugar, para que ningún nivel cambie de lado por error.
        """
        modelo, poligonos, niveles = cls._cargar(id_modelo2d)
        polygon = cls._buscar(poligonos, id_poligono, "polígono")

        puntos = cls._normalize_points(polygon.get("puntos") or [])
        n = len(puntos)

        if n < 3:
            raise ValueError(f"El polígono '{id_poligono}' no tiene lados válidos.")

        clic = cls._normalize_point(punto)

        if indice is None:
            lado = NivelesUtils.lado_mas_cercano(puntos, clic["x"], clic["y"])["lado"]
        else:
            try:
                indice = int(indice)
            except (TypeError, ValueError):
                raise ValueError("El índice del vértice debe ser un número entero.")

            if not 1 <= indice <= n:
                raise ValueError(f"El índice del vértice debe estar entre 1 y {n}.")

            lado = indice - 1

        proyectado = NivelesUtils.lado_info(puntos, lado, clic["x"], clic["y"])["punto"]
        nuevo = {"x": float(proyectado["x"]), "y": float(proyectado["y"])}

        for existente in (puntos[lado], puntos[(lado + 1) % n]):
            if (
                abs(existente["x"] - nuevo["x"]) < 1e-9
                and abs(existente["y"] - nuevo["y"]) < 1e-9
            ):
                raise ValueError("Ya existe un vértice en ese punto.")

        puntos.insert(lado + 1, nuevo)

        cls._aplicar_puntos(polygon, puntos, id_poligono)

        def nuevo_lado(nivel: Dict[str, Any], actual: int) -> int:
            if actual < lado:
                return actual

            if actual > lado:
                return actual + 1

            # Estaba en el lado que se partió: queda en la mitad más cercana.
            x, y = float(nivel.get("x", 0.0)), float(nivel.get("y", 0.0))
            d1 = NivelesUtils.lado_info(puntos, lado, x, y)["distancia"]
            d2 = NivelesUtils.lado_info(puntos, lado + 1, x, y)["distancia"]

            return lado if d1 <= d2 else lado + 1

        cls._remapear_lados(niveles, id_poligono, nuevo_lado)
        cls._ajustar_tipo(polygon)

        if not cls._guardar(id_modelo2d, modelo, poligonos, niveles):
            raise ValueError("No se pudo guardar el vértice.")

        return polygon

    @classmethod
    @_con_lock_modelo
    def eliminar_vertice_poligono(
        cls,
        id_modelo2d: str,
        id_poligono: str,
        indice: int,
    ) -> Dict[str, Any]:
        """
        Elimina el vértice `indice` (0..n-1). El polígono conserva al menos 3.

        Los dos lados que tocaban ese vértice se fusionan en uno solo; los
        niveles asociados a cualquiera de los dos pasan al lado fusionado y
        los lados siguientes se corren un lugar hacia atrás.
        """
        modelo, poligonos, niveles = cls._cargar(id_modelo2d)
        polygon = cls._buscar(poligonos, id_poligono, "polígono")

        puntos = cls._normalize_points(polygon.get("puntos") or [])
        n = len(puntos)

        try:
            k = int(indice)
        except (TypeError, ValueError):
            raise ValueError("El índice del vértice debe ser un número entero.")

        if not 0 <= k < n:
            raise ValueError(f"El vértice debe estar entre 0 y {n - 1}.")

        if n <= 3:
            raise ValueError("Un polígono debe conservar al menos 3 vértices.")

        del puntos[k]

        cls._aplicar_puntos(polygon, puntos, id_poligono)

        fusionados = {(k - 1) % n, k}
        fusionado = (k - 1) % (n - 1)

        def nuevo_lado(nivel: Dict[str, Any], actual: int) -> int:
            if actual in fusionados:
                return fusionado

            return actual - 1 if actual > k else actual

        cls._remapear_lados(niveles, id_poligono, nuevo_lado)
        cls._ajustar_tipo(polygon)

        if not cls._guardar(id_modelo2d, modelo, poligonos, niveles):
            raise ValueError("No se pudo eliminar el vértice.")

        return polygon

    # =========================================================
    # NIVELES
    # =========================================================

    @staticmethod
    def _validar_valor_nivel(valor: Any) -> float:
        try:
            valor = float(valor)
        except (TypeError, ValueError):
            raise ValueError("El valor del nivel debe ser numérico.")

        if not NivelesUtils.NIVEL_MINIMO <= valor <= NivelesUtils.NIVEL_MAXIMO:
            raise ValueError("El nivel debe estar entre -100 y 100 metros.")

        return valor

    @staticmethod
    def _asociar(
        poligono: Dict[str, Any],
        nivel: Dict[str, Any],
        lado: Optional[int] = None,
    ) -> None:
        """
        Asocia el nivel a un lado del polígono. Sin `lado`, usa el lado más
        cercano a la posición del nivel. Si el nivel ya estaba asociado a
        ese polígono, solo cambia el lado.
        """
        puntos = poligono.get("puntos") or []

        if len(puntos) < 3:
            raise ValueError(
                f"El polígono '{poligono.get('id')}' no tiene lados válidos."
            )

        if lado is None:
            lado = NivelesUtils.lado_mas_cercano(
                puntos, float(nivel.get("x", 0.0)), float(nivel.get("y", 0.0))
            )["lado"]
        else:
            try:
                lado = int(lado)
            except (TypeError, ValueError):
                raise ValueError("El lado debe ser un número entero.")

            if not 0 <= lado < len(puntos):
                raise ValueError(
                    f"El lado debe estar entre 0 y {len(puntos) - 1}."
                )

        pid = str(poligono.get("id"))

        asociaciones = [
            a
            for a in nivel.get("asociaciones") or []
            if str(a.get("id_poligono")) != pid
        ]
        asociaciones.append({"id_poligono": pid, "lado": lado})
        nivel["asociaciones"] = asociaciones

    @classmethod
    @_con_lock_modelo
    def crear_nivel(
        cls,
        id_modelo2d: str,
        valor: float,
        punto_seleccionado: Dict[str, Any],
        texto: Optional[str] = None,
        page: int = 0,
        capa: Optional[str] = None,
        id_poligono: Optional[str] = None,
        lado: Optional[int] = None,
        asociar_automaticamente: bool = True,
    ) -> Dict[str, Any]:
        """
        Crea un nivel manual en el punto elegido en el visor.

        - Con `id_poligono` (y opcionalmente `lado`) queda asociado ahí.
        - Sin `id_poligono` y con `asociar_automaticamente`, se asocia al lado
          más cercano si hay un polígono cerca (mismo criterio que el
          intérprete).
        - Si no hay ninguno cerca queda SIN ASOCIAR ("asociado": False) y se
          puede asociar después con asociar_nivel_poligono. No genera
          pendiente hasta que se asocie.
        """
        modelo, poligonos, niveles = cls._cargar(id_modelo2d)

        valor = cls._validar_valor_nivel(valor)
        punto = cls._normalize_selected_point(punto_seleccionado)
        nivel_capa = cls._capa_para_nivel(modelo, capa)

        nuevo_nivel = {
            "id": f"manual_nivel_{uuid.uuid4().hex[:12]}",
            "valor": valor,
            "texto": str(texto if texto is not None else f"{valor:+.2f}"),
            "x": punto["x"],
            "y": punto["y"],
            "posicion": {"x": punto["x"], "y": punto["y"]},
            "page": int(page),
            "capa": nivel_capa,
            "origen": "manual",
            "asociaciones": [],
            "asociado": False,
        }

        if id_poligono:
            cls._asociar(cls._buscar(poligonos, id_poligono, "polígono"), nuevo_nivel, lado)

        elif asociar_automaticamente:
            asociacion = NivelesUtils.buscar_asociacion_automatica(
                nuevo_nivel, poligonos
            )

            if asociacion:
                nuevo_nivel["asociaciones"] = [
                    {
                        "id_poligono": asociacion["id_poligono"],
                        "lado": asociacion["lado"],
                    }
                ]

        niveles.append(nuevo_nivel)

        if not cls._guardar(
            id_modelo2d, modelo, poligonos, niveles, capas=modelo.get("capas")
        ):
            raise ValueError("No se pudo guardar el nivel.")

        # _guardar ya actualizó "asociaciones"/"asociado" sobre este mismo dict.
        return {"mensaje": "Nivel creado correctamente.", "nivel": nuevo_nivel}

    @classmethod
    @_con_lock_modelo
    def actualizar_nivel(
        cls,
        id_modelo2d: str,
        id_nivel: str,
        datos: Dict[str, Any],
    ) -> Dict[str, Any]:
        modelo, poligonos, niveles = cls._cargar(id_modelo2d)
        nivel = cls._buscar(niveles, id_nivel, "nivel")

        if "valor" in datos:
            nivel["valor"] = cls._validar_valor_nivel(datos["valor"])

        if "texto" in datos:
            nivel["texto"] = str(datos["texto"])

        if "punto_seleccionado" in datos:
            punto = cls._normalize_selected_point(datos["punto_seleccionado"])

            nivel["x"] = punto["x"]
            nivel["y"] = punto["y"]

            # Se movió el nivel: cada asociación vuelve a buscar su lado más
            # cercano al guardar.
            for asociacion in nivel.get("asociaciones") or []:
                asociacion["lado"] = None

        if "page" in datos:
            nivel["page"] = int(datos["page"])

        if "capa" in datos:
            nivel["capa"] = cls._validate_existing_layer(modelo, datos["capa"])

        nivel["posicion"] = {
            "x": float(nivel.get("x", 0)),
            "y": float(nivel.get("y", 0)),
        }

        if not cls._guardar(id_modelo2d, modelo, poligonos, niveles):
            raise ValueError("No se pudo actualizar el nivel.")

        return {"mensaje": "Nivel actualizado correctamente.", "nivel": nivel}

    @classmethod
    @_con_lock_modelo
    def eliminar_nivel(cls, id_modelo2d: str, id_nivel: str) -> Dict[str, Any]:
        modelo, poligonos, niveles = cls._cargar(id_modelo2d)
        nivel = cls._buscar(niveles, id_nivel, "nivel")

        niveles = [n for n in niveles if n is not nivel]

        # _guardar regenera los polígonos: el nivel desaparece de todos.
        if not cls._guardar(id_modelo2d, modelo, poligonos, niveles):
            raise ValueError("No se pudo eliminar el nivel.")

        return {"mensaje": "Nivel eliminado correctamente.", "nivel": nivel}

    # =========================================================
    # ASOCIAR / DESASOCIAR NIVEL <-> LADO DE POLÍGONO
    # =========================================================

    @classmethod
    @_con_lock_modelo
    def asociar_nivel_poligono(
        cls,
        id_modelo2d: str,
        id_poligono: str,
        id_nivel: str,
        lado: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Asocia un nivel (reconocido o creado) a un lado del polígono.

        `lado` es el índice de la arista (puntos[lado] -> puntos[lado + 1]).
        Si no se envía, se usa el lado más cercano al nivel. Un nivel puede
        estar asociado a más de un polígono (p. ej. lado compartido); si ya
        estaba asociado a ESTE polígono, solo se cambia el lado.
        """
        modelo, poligonos, niveles = cls._cargar(id_modelo2d)

        poligono = cls._buscar(poligonos, id_poligono, "polígono")
        nivel = cls._buscar(niveles, id_nivel, "nivel")

        cls._asociar(poligono, nivel, lado)

        return cls._guardar(id_modelo2d, modelo, poligonos, niveles) or modelo

    @classmethod
    @_con_lock_modelo
    def desasociar_nivel_poligono(
        cls,
        id_modelo2d: str,
        id_poligono: str,
        id_nivel: str,
    ) -> Dict[str, Any]:
        """
        Saca el nivel de ese polígono. Sirve para niveles reconocidos y
        creados. El nivel NO se borra: queda sin asociar y se puede asociar
        de nuevo (a otro polígono o lado) o eliminar con eliminar_nivel.
        """
        modelo, poligonos, niveles = cls._cargar(id_modelo2d)

        cls._buscar(poligonos, id_poligono, "polígono")
        nivel = cls._buscar(niveles, id_nivel, "nivel")

        nivel["asociaciones"] = [
            a
            for a in nivel.get("asociaciones") or []
            if str(a.get("id_poligono")) != str(id_poligono)
        ]

        return cls._guardar(id_modelo2d, modelo, poligonos, niveles) or modelo

    # =========================================================
    # VALIDACIÓN
    # =========================================================

    @staticmethod
    def _punto_a_tupla(punto: Any, polygon_id: Any) -> Tuple[float, float]:
        """Punto {x, y} o [x, y] -> (x, y), con los mensajes de validación."""
        if isinstance(punto, dict):
            if "x" not in punto or "y" not in punto:
                raise ValueError(
                    f"El polígono '{polygon_id}' contiene un punto sin coordenadas x/y."
                )
            crudo = (punto["x"], punto["y"])

        elif isinstance(punto, (list, tuple)):
            if len(punto) < 2:
                raise ValueError(
                    f"El polígono '{polygon_id}' tiene un punto incompleto."
                )
            crudo = (punto[0], punto[1])

        else:
            raise ValueError(
                f"Formato de punto no reconocido en el polígono '{polygon_id}'."
            )

        try:
            return float(crudo[0]), float(crudo[1])
        except (TypeError, ValueError):
            raise ValueError(f"Coordenadas inválidas en el polígono '{polygon_id}'.")

    @classmethod
    def validar_modelo2d(cls, id_modelo2d: str) -> None:
        modelo = cls._get_modelo2d(id_modelo2d)
        poligonos = modelo.get("poligonos") or []

        if not poligonos:
            raise ValueError(
                f"El modelo 2D '{id_modelo2d}' no tiene polígonos para validar."
            )

        for polygon in poligonos:
            polygon_id = polygon.get("id", "sin_id")
            puntos = (
                polygon.get("puntos")
                or polygon.get("points")
                or polygon.get("footprint")
                or []
            )

            if not isinstance(puntos, list):
                raise ValueError(
                    f"El polígono '{polygon_id}' no contiene una lista de puntos válida."
                )

            if len(puntos) < 3:
                raise ValueError(
                    f"El polígono '{polygon_id}' debe tener al menos 3 puntos."
                )

            coordenadas = [
                cls._punto_a_tupla(punto, polygon_id) for punto in puntos
            ]

            try:
                geometria = Polygon(coordenadas).buffer(0)
            except Exception as exc:
                raise ValueError(
                    f"Error construyendo la geometría del polígono '{polygon_id}': {exc}"
                )

            if geometria.is_empty:
                raise ValueError(
                    f"El polígono '{polygon_id}' tiene una geometría vacía."
                )

            if geometria.area <= 1e-9:
                raise ValueError(
                    f"El polígono '{polygon_id}' tiene un área inválida o cruzada (cero)."
                )

        PlanoRepository.update_modelo2d(id_modelo2d=id_modelo2d, validado=True)

    # =========================================================
    # OBTENER MODELO
    # =========================================================

    @classmethod
    def obtener_modelo2d(cls, id_modelo2d: str) -> Dict[str, Any]:
        modelo, _, _ = cls._cargar(id_modelo2d)
        return modelo