"""
Lógica compartida entre PDFInterpreterService y EditorModelo2DService.

Ambos servicios tienen que producir exactamente la misma estructura de
niveles y asociaciones; por eso esta lógica vive en un solo lugar.

MODELO DE DATOS
---------------

Modelo2D["cotas_altura"]  ->  FUENTE DE VERDAD de los niveles:

    {
        "id": "p0-nivel-003" | "manual_nivel_ab12cd34ef56",
        "valor": 7.9,
        "texto": "+ 7.90",
        "x": 123.4, "y": 456.7,
        "posicion": {"x": 123.4, "y": 456.7},
        "page": 0,
        "capa": "LEVELS",
        "origen": "texto" | "manual",       # reconocido por el intérprete / creado a mano
        "asociaciones": [                   # a qué lado de qué polígono pertenece
            {"id_poligono": "roof_004", "lado": 2}
        ],
        "asociado": True,                   # derivado: len(asociaciones) > 0
    }

Modelo2D["poligonos"][i]["niveles"]  ->  COPIAS derivadas (se regeneran siempre
con reconstruir_niveles_poligonos, nunca se editan a mano). Cada copia agrega:

    "id_poligono", "lado", "distancia_lado", "punto_lado"

"lado" = índice de la arista i del polígono: va de puntos[i] a puntos[i+1]
(el último lado une el último punto con el primero).

Además, cada polígono queda con nivel_bajo / nivel_medio / nivel_alto,
tipo_cubierta y "pendiente" (lados bajo/alto y desnivel) listos para el
generador 3D.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

Punto = Tuple[float, float]


class NivelesUtils:

    NIVEL_MINIMO = -100.0
    NIVEL_MAXIMO = 100.0

    # Distancia máxima (en puntos PDF) entre el nivel y el lado más cercano de
    # un polígono para considerarlos asociados. Un nivel que cae DENTRO de un
    # polígono siempre se asocia, sin importar esta distancia.
    DISTANCIA_MAXIMA_LADO = 40.0

    # Valores de tipo_cubierta que se recalculan solos. Si el usuario puso otro
    # valor a mano, no se pisa.
    TIPOS_CUBIERTA_AUTOMATICOS = frozenset(
        {
            "pendiente_por_resolver",
            "nivel_medio_pendiente",
            "pendiente_entre_niveles",
            "pendiente_con_nivel_medio",
        }
    )

    # ------------------------------------------------------------------
    # GEOMETRÍA (Python puro)
    # ------------------------------------------------------------------

    @staticmethod
    def punto_mas_cercano_en_segmento(
        p: Punto, a: Punto, b: Punto
    ) -> Tuple[Punto, float]:
        """Devuelve (punto más cercano sobre el segmento a-b, distancia)."""
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        largo2 = dx * dx + dy * dy

        if largo2 <= 0.0:
            return (ax, ay), math.hypot(p[0] - ax, p[1] - ay)

        t = ((p[0] - ax) * dx + (p[1] - ay) * dy) / largo2
        t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t

        qx, qy = ax + t * dx, ay + t * dy
        return (qx, qy), math.hypot(p[0] - qx, p[1] - qy)

    @staticmethod
    def coordenadas(puntos: Sequence[Any]) -> List[Punto]:
        resultado: List[Punto] = []

        for punto in puntos or []:
            if isinstance(punto, dict):
                resultado.append((float(punto["x"]), float(punto["y"])))
            else:
                resultado.append((float(punto[0]), float(punto[1])))

        return resultado

    @staticmethod
    def _info_lado(
        coords: List[Punto], lado: int, x: float, y: float
    ) -> Dict[str, Any]:
        a = coords[lado]
        b = coords[(lado + 1) % len(coords)]
        q, d = NivelesUtils.punto_mas_cercano_en_segmento((x, y), a, b)

        return {
            "lado": lado,
            "distancia": d,
            "punto": {"x": q[0], "y": q[1]},
            "arista": {
                "p1": {"x": a[0], "y": a[1]},
                "p2": {"x": b[0], "y": b[1]},
            },
        }

    @classmethod
    def lado_info(
        cls, puntos: Sequence[Any], lado: int, x: float, y: float
    ) -> Optional[Dict[str, Any]]:
        """Distancia y punto proyectado del punto (x, y) sobre un lado dado."""
        coords = cls.coordenadas(puntos)

        if len(coords) < 3 or not 0 <= lado < len(coords):
            return None

        return cls._info_lado(coords, lado, x, y)

    @classmethod
    def lado_mas_cercano(
        cls, puntos: Sequence[Any], x: float, y: float
    ) -> Optional[Dict[str, Any]]:
        """Lado del polígono más cercano al punto (x, y)."""
        coords = cls.coordenadas(puntos)

        if len(coords) < 3:
            return None

        mejor = None

        for i in range(len(coords)):
            info = cls._info_lado(coords, i, x, y)

            if mejor is None or info["distancia"] < mejor["distancia"]:
                mejor = info

        return mejor

    @classmethod
    def punto_dentro(cls, puntos: Sequence[Any], x: float, y: float) -> bool:
        """Punto en polígono (ray casting)."""
        coords = cls.coordenadas(puntos)
        dentro = False
        j = len(coords) - 1

        for i in range(len(coords)):
            xi, yi = coords[i]
            xj, yj = coords[j]

            if (yi > y) != (yj > y):
                if x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                    dentro = not dentro

            j = i

        return dentro

    @staticmethod
    def _como_lado(valor: Any) -> Optional[int]:
        if isinstance(valor, bool):
            return None
        if isinstance(valor, int):
            return valor
        if isinstance(valor, float) and valor.is_integer():
            return int(valor)
        return None

    # ------------------------------------------------------------------
    # ASOCIACIÓN AUTOMÁTICA NIVEL -> LADO DE POLÍGONO
    # ------------------------------------------------------------------

    @classmethod
    def buscar_asociacion_automatica(
        cls,
        nivel: Dict[str, Any],
        poligonos: List[Dict[str, Any]],
        distancia_maxima: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Busca el (polígono, lado) al que pertenece un nivel.

        - Solo considera polígonos de la misma página.
        - Un nivel dentro del polígono o a <= distancia_maxima de alguno de
          sus lados es candidato.
        - Gana el lado más cercano. En empate (lado compartido entre dos
          polígonos) gana el polígono que contiene al nivel y después el de
          menor área.

        Devuelve None si no hay ningún polígono cerca.
        """
        limite = (
            cls.DISTANCIA_MAXIMA_LADO
            if distancia_maxima is None
            else float(distancia_maxima)
        )

        x = float(nivel.get("x", 0.0))
        y = float(nivel.get("y", 0.0))
        pagina = int(nivel.get("page", 0) or 0)

        mejor = None

        for poligono in poligonos:
            if int(poligono.get("page", 0) or 0) != pagina:
                continue

            puntos = poligono.get("puntos") or []

            if len(puntos) < 3:
                continue

            cercano = cls.lado_mas_cercano(puntos, x, y)
            dentro = cls.punto_dentro(puntos, x, y)

            if not dentro and cercano["distancia"] > limite:
                continue

            clave = (
                round(cercano["distancia"], 3),
                0 if dentro else 1,
                float(poligono.get("area") or 0.0),
            )

            if mejor is None or clave < mejor[0]:
                mejor = (clave, poligono, cercano, dentro)

        if mejor is None:
            return None

        _, poligono, cercano, dentro = mejor

        return {
            "id_poligono": str(poligono.get("id")),
            "lado": cercano["lado"],
            "distancia": cercano["distancia"],
            "dentro": dentro,
        }

    @classmethod
    def asociar_niveles_automaticamente(
        cls,
        poligonos: List[Dict[str, Any]],
        niveles: List[Dict[str, Any]],
        distancia_maxima: Optional[float] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Asocia cada nivel a un lado de polígono. Los niveles sin polígono
        cerca NO se devuelven en la primera lista: quedan eliminados y se
        informan en la segunda (solo como registro).
        """
        asociados: List[Dict[str, Any]] = []
        descartados: List[Dict[str, Any]] = []

        for nivel in niveles:
            asociacion = cls.buscar_asociacion_automatica(
                nivel, poligonos, distancia_maxima
            )

            if asociacion is None:
                descartados.append(
                    {
                        "id": nivel.get("id"),
                        "valor": nivel.get("valor"),
                        "texto": nivel.get("texto"),
                        "x": nivel.get("x"),
                        "y": nivel.get("y"),
                        "page": nivel.get("page"),
                        "motivo": "sin_poligono_cercano",
                    }
                )
                continue

            nivel["asociaciones"] = [
                {
                    "id_poligono": asociacion["id_poligono"],
                    "lado": asociacion["lado"],
                }
            ]
            nivel["asociado"] = True
            asociados.append(nivel)

        return asociados, descartados

    # ------------------------------------------------------------------
    # DERIVADOS EN EL POLÍGONO
    # ------------------------------------------------------------------

    @classmethod
    def reconstruir_niveles_poligonos(
        cls,
        poligonos: List[Dict[str, Any]],
        niveles: List[Dict[str, Any]],
    ) -> None:
        """
        Regenera polygon["niveles"], nivel_bajo/medio/alto, tipo_cubierta y
        pendiente a partir de nivel["asociaciones"] (fuente de verdad).

        También limpia asociaciones huérfanas (polígono borrado) y recalcula
        el lado cuando es None o quedó fuera de rango (por ejemplo después de
        editar los puntos del polígono o mover el nivel).
        """
        indice = {str(p.get("id")): p for p in poligonos}
        por_poligono: Dict[str, List[Dict[str, Any]]] = {
            pid: [] for pid in indice
        }

        for nivel in niveles:
            x = float(nivel.get("x", 0.0))
            y = float(nivel.get("y", 0.0))

            vigentes: List[Dict[str, Any]] = []
            vistos = set()

            for asociacion in nivel.get("asociaciones") or []:
                pid = str(asociacion.get("id_poligono"))
                poligono = indice.get(pid)

                if poligono is None or pid in vistos:
                    continue

                puntos = poligono.get("puntos") or []

                if len(puntos) < 3:
                    continue

                lado = cls._como_lado(asociacion.get("lado"))

                if lado is None or not 0 <= lado < len(puntos):
                    lado = cls.lado_mas_cercano(puntos, x, y)["lado"]

                info = cls.lado_info(puntos, lado, x, y)

                vistos.add(pid)
                vigentes.append({"id_poligono": pid, "lado": lado})

                copia = {
                    k: v
                    for k, v in nivel.items()
                    if k not in ("asociaciones", "asociado")
                }
                copia.update(
                    {
                        "id_poligono": pid,
                        "lado": lado,
                        "distancia_lado": round(info["distancia"], 4),
                        "punto_lado": info["punto"],
                    }
                )
                por_poligono[pid].append(copia)

            nivel["asociaciones"] = vigentes
            nivel["asociado"] = bool(vigentes)

        for pid, poligono in indice.items():
            poligono["niveles"] = sorted(
                por_poligono[pid], key=lambda n: float(n.get("valor", 0.0))
            )
            cls.recalcular_niveles_poligono(poligono)

    @classmethod
    def recalcular_niveles_poligono(cls, poligono: Dict[str, Any]) -> None:
        """
        Clasifica los niveles asociados al polígono:

            0 niveles  -> pendiente_por_resolver
            1 nivel    -> nivel_medio_pendiente
            2 niveles  -> menor = bajo, mayor = alto
            3 o más    -> bajo, alto y el más cercano al punto medio = medio
        """
        ordenados = sorted(
            poligono.get("niveles") or [],
            key=lambda n: float(n.get("valor", 0.0)),
        )

        bajo = medio = alto = None

        if len(ordenados) == 1:
            medio = ordenados[0]

        elif len(ordenados) == 2:
            bajo, alto = ordenados

        elif len(ordenados) >= 3:
            bajo, alto = ordenados[0], ordenados[-1]
            objetivo = (float(bajo["valor"]) + float(alto["valor"])) / 2.0
            medio = min(
                ordenados[1:-1],
                key=lambda n: abs(float(n["valor"]) - objetivo),
            )

        poligono["nivel_bajo"] = bajo
        poligono["nivel_medio"] = medio
        poligono["nivel_alto"] = alto

        tipo_actual = poligono.get("tipo_cubierta")

        if not tipo_actual or tipo_actual in cls.TIPOS_CUBIERTA_AUTOMATICOS:
            if not ordenados:
                tipo = "pendiente_por_resolver"
            elif len(ordenados) == 1:
                tipo = "nivel_medio_pendiente"
            elif len(ordenados) == 2:
                tipo = "pendiente_entre_niveles"
            else:
                tipo = "pendiente_con_nivel_medio"

            poligono["tipo_cubierta"] = tipo

        # Datos para que el generador 3D arme el plano inclinado a partir de
        # los lados que tienen nivel.
        lado_bajo = bajo.get("lado") if bajo else None
        lado_alto = alto.get("lado") if alto else None

        poligono["pendiente"] = {
            "lado_bajo": lado_bajo,
            "lado_medio": medio.get("lado") if medio else None,
            "lado_alto": lado_alto,
            "desnivel": (
                float(alto["valor"]) - float(bajo["valor"])
                if bajo and alto
                else None
            ),
            "definida": bool(
                bajo and alto and lado_bajo is not None
                and lado_bajo != lado_alto
            ),
        }

    # ------------------------------------------------------------------
    # COMPATIBILIDAD CON MODELOS GUARDADOS ANTES DE ESTE CAMBIO
    # ------------------------------------------------------------------

    @classmethod
    def migrar_formato_anterior(
        cls,
        poligonos: List[Dict[str, Any]],
        niveles: List[Dict[str, Any]],
    ) -> bool:
        """
        Los niveles viejos no tienen "asociaciones": se arman a partir de las
        copias que tenía cada polígono. El lado se calcula después, en
        reconstruir_niveles_poligonos. Devuelve True si migró algo.
        """
        pendientes = [n for n in niveles if "asociaciones" not in n]

        if not pendientes:
            return False

        por_nivel: Dict[str, List[str]] = {}

        for poligono in poligonos:
            for item in poligono.get("niveles") or []:
                nid = str(item.get("id") if isinstance(item, dict) else item)
                por_nivel.setdefault(nid, []).append(str(poligono.get("id")))

        for nivel in pendientes:
            nivel["asociaciones"] = [
                {"id_poligono": pid, "lado": None}
                for pid in por_nivel.get(str(nivel.get("id")), [])
            ]

        cls.reconstruir_niveles_poligonos(poligonos, niveles)
        return True
