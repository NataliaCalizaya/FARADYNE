import math
from typing import Any, Dict, List, Optional, Tuple


def calculate_equivalent_collection_area_ae(length: float, width: float, height: float) -> float:
    """Pure function: Calculates equivalent collection area Ae (m²) according to IEC 62305-2 / IRAM 2184-2.
    Formula: Ae = (L * W) + 2 * H * (L + W) + pi * H^2
    """
    if length <= 0 or width <= 0 or height <= 0:
        return 0.0
    area_base = length * width
    area_perimeter = 2.0 * height * (length + width)
    area_corners = math.pi * (height ** 2)
    return round(area_base + area_perimeter + area_corners, 2)


def calculate_direct_strikes_nd(density_ng: float, area_ae: float, factor_cd: float = 1.0) -> float:
    """Pure function: Calculates expected annual direct lightning strikes Nd.
    Formula: Nd = Ng * Ae * Cd * 10^-6
    """
    return round(density_ng * area_ae * factor_cd * 1e-6, 6)


def calculate_tolerable_strikes_nc(
    factor_cb: float = 1.0,
    factor_cc: float = 1.0,
    factor_cd: float = 1.0,
    factor_ce: float = 1.0,
) -> float:
    """Pure function: Calculates tolerable annual lightning strike frequency limit Nc.
    Formula: Nc = 1.5 * 10^-3 / (Cb * Cc * Cd * Ce)
    """
    denominator = factor_cb * factor_cc * factor_cd * factor_ce
    if denominator <= 0:
        denominator = 1.0
    return round(1.5e-3 / denominator, 6)


def determine_spcr_level(nd, nc):
    if nd <= nc or nd <= 0:
        return False, "IV", 0.80, 60.0

    efficiency = 1.0 - (nc / nd)

    if efficiency >= 0.98:
        return True, "I", 0.98, 20.0
    elif efficiency >= 0.95:
        return True, "II", 0.95, 30.0
    elif efficiency >= 0.90:
        return True, "III", 0.90, 45.0
    else:
        return True, "IV", 0.80, 60.0

def check_point_coverage_rolling_sphere(
    point: Tuple[float, float, float],
    masts: List[Dict[str, Any]],
    rolling_sphere_radius: float = 30.0,
) -> Tuple[bool, float, Optional[str]]:
    """Pure function: Checks if a 3D point (x,y,z) is protected by any of the masts using the Rolling Sphere Method.
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
    """Service to execute IEC 62305 / IRAM 2184 SPDA risk calculations and coverage validation."""

    @staticmethod
    def calculate_risk(
        length: float,
        width: float,
        height: float,
        density_ng: float,
        factor_cd: float = 1.0,
        factor_cb: float = 1.0,
        factor_cc: float = 1.0,
        factor_ce: float = 1.0,
    ) -> Dict[str, Any]:
        """Calculates Ae, Nd, Nc, and SPCR requirement for building dimensions and environmental factors."""
        ae = calculate_equivalent_collection_area_ae(length, width, height)
        nd = calculate_direct_strikes_nd(density_ng, ae, factor_cd)
        nc = calculate_tolerable_strikes_nc(factor_cb, factor_cc, factor_cd, factor_ce)
        requiere_spcr, nivel, eficiencia, radio_r = determine_spcr_level(nd, nc)

        return {
            "longitud": length,
            "anchura": width,
            "altura": height,
            "area_equivalente_ae": ae,
            "frecuencia_impactos_nd": nd,
            "frecuencia_tolerable_nc": nc,
            "requiere_spcr": requiere_spcr,
            "nivel_proteccion_calculado": nivel,
            "eficiencia_proteccion": eficiencia,
            "radio_esfera_rodante_r": radio_r,
            "factores_riesgo": {
                "density_ng": density_ng,
                "factor_cd": factor_cd,
                "factor_cb": factor_cb,
                "factor_cc": factor_cc,
                "factor_ce": factor_ce,
            },
        }

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
        cov_percent = round((len(puntos_cobertura) / total_pts) * 100.0, 2) if total_pts > 0 else 0.0

        advertencias = []
        if len(masts) == 0:
            advertencias.append("No se ha colocado ningún mástil captor en la estructura.")
        elif cov_percent < 100.0:
            advertencias.append(
                f"La cobertura es del {cov_percent}%. Existen {len(puntos_desprotegidos)} puntos de la cubierta sin protección contra descargas atmosféricas."
            )

        return {
            "radio_esfera_rodante_r": rolling_sphere_radius,
            "total_mastiIes": len(masts),
            "puntos_cobertura": puntos_cobertura,
            "puntos_desprotegidos": puntos_desprotegidos,
            "porcentaje_cobertura": cov_percent,
            "advertencias": advertencias,
        }
