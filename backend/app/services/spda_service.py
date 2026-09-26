"""
app.services.spda_service

Servicio de evaluación de cobertura de mástiles captores (HU05) mediante el
Método de la Esfera Rodante. Lo usa el router de mástiles para verificar
qué puntos de la envolvente del edificio quedan protegidos por los mástiles
ya colocados, usando como radio el que corresponde al Nivel de Protección
calculado en HU04 (ver app.services.level_protection_service).
"""

import math
from typing import Any, Dict, List, Optional, Tuple


def check_point_coverage_rolling_sphere(
    point: Tuple[float, float, float],
    masts: List[Dict[str, Any]],
    rolling_sphere_radius: float = 30.0,
) -> Tuple[bool, float, Optional[str]]:
    """Pure function: Checks if a 3D point (x,y,z) is protected by any of the
    masts using the Rolling Sphere Method.

    Returns (is_protected, min_distance_to_mast, protective_mast_id).
    """
    px, py, pz = point
    is_protected = False
    min_dist = float("inf")
    best_mast_id = None

    r = rolling_sphere_radius

    for mast in masts:
        mx = float(mast.get("posicion_x", 0.0))
        my = float(mast.get("posicion_y", 0.0))
        mz = float(mast.get("posicion_z", 0.0))
        h = float(mast.get("altura", 0.0))
        mast_id = str(mast.get("id", ""))

        tip_z = mz + h
        dist_2d = math.hypot(px - mx, py - my)
        min_dist = min(min_dist, dist_2d)

        # Rolling sphere coverage check
        if dist_2d <= r:
            # Protected surface height under sphere resting on mast tip
            # Z_prot = tip_z + sqrt(R^2 - d^2) - R
            rad_arg = (r ** 2) - (dist_2d ** 2)
            if rad_arg >= 0:
                z_prot = tip_z + math.sqrt(rad_arg) - r
                if pz <= z_prot + 0.05:  # 5cm margin
                    is_protected = True
                    best_mast_id = mast_id
                    break

    return is_protected, round(min_dist, 2), best_mast_id


class SPDAService:
    """Servicio de evaluación de cobertura de mástiles (HU05)."""

    @staticmethod
    def evaluate_masts_coverage(
        masts: List[Dict[str, Any]],
        building_dim: Dict[str, Any],
        rolling_sphere_radius: float = 30.0,
    ) -> Dict[str, Any]:
        """Evaluates 3D grid coverage over building envelope for placed masts."""
        length = float(building_dim.get("longitud", 20.0))
        width = float(building_dim.get("anchura", 15.0))
        height = float(building_dim.get("altura", 7.5))

        # Sample grid of critical building roof/corner vertices
        steps_x = max(2, int(length // 2))
        steps_y = max(2, int(width // 2))

        grid_points = []
        for ix in range(steps_x + 1):
            x = (length / steps_x) * ix
            for iy in range(steps_y + 1):
                y = (width / steps_y) * iy
                # Roof top point
                grid_points.append((x, y, height))

        puntos_cobertura = []
        puntos_desprotegidos = []

        for pt in grid_points:
            protected, min_d, mast_id = check_point_coverage_rolling_sphere(
                pt, masts, rolling_sphere_radius
            )
            item = {
                "x": pt[0],
                "y": pt[1],
                "z": pt[2],
                "protegido": protected,
                "distancia_minima_mastil": min_d,
                "mastil_cobertura_id": mast_id,
            }
            if protected:
                puntos_cobertura.append(item)
            else:
                puntos_desprotegidos.append(item)

        total_pts = len(grid_points)
        cov_percent = (
            round((len(puntos_cobertura) / total_pts) * 100.0, 2) if total_pts > 0 else 0.0
        )

        advertencias = []
        if len(masts) == 0:
            advertencias.append("No se ha colocado ningún mástil captor en la estructura.")
        elif cov_percent < 100.0:
            advertencias.append(
                f"La cobertura es del {cov_percent}%. Existen {len(puntos_desprotegidos)} "
                "puntos de la cubierta sin protección contra descargas atmosféricas."
            )

        return {
            "radio_esfera_rodante_r": rolling_sphere_radius,
            "total_mastiIes": len(masts),
            "puntos_cobertura": puntos_cobertura,
            "puntos_desprotegidos": puntos_desprotegidos,
            "porcentaje_cobertura": cov_percent,
            "advertencias": advertencias,
        }