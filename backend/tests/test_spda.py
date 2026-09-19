import pytest
from app.services.spda_service import (
    SPDAService,
    calculate_direct_strikes_nd,
    calculate_equivalent_collection_area_ae,
    calculate_tolerable_strikes_nc,
    check_point_coverage_rolling_sphere,
    determine_spcr_level,
)


def test_calculate_equivalent_collection_area_ae():
    """Test equivalent collection area Ae for a 20m x 15m x 10m building."""
    # Ae = (20*15) + 2*10*(20+15) + pi*(10^2)
    # Ae = 300 + 700 + 314.159 = 1314.16 m²
    ae = calculate_equivalent_collection_area_ae(length=20.0, width=15.0, height=10.0)
    assert pytest.approx(ae, 0.1) == 1314.16


def test_calculate_direct_strikes_nd():
    """Test direct strike frequency Nd for Ng=2.5, Ae=1314.16, Cd=1.0."""
    # Nd = 2.5 * 1314.16 * 1.0 * 1e-6 = 0.003285
    nd = calculate_direct_strikes_nd(density_ng=2.5, area_ae=1314.16, factor_cd=1.0)
    assert pytest.approx(nd, 1e-5) == 0.003285


def test_calculate_tolerable_strikes_nc():
    """Test tolerable strike frequency Nc."""
    # Nc = 1.5e-3 / (1 * 1 * 1 * 1) = 0.0015
    nc = calculate_tolerable_strikes_nc()
    assert pytest.approx(nc, 1e-5) == 0.0015


def test_determine_spcr_level():
    """Test SPCR requirement decision and level classification."""
    # Nd = 0.003285, Nc = 0.0015 -> Nd > Nc -> SPCR Required!
    # Efficiency E = 1 - (0.0015 / 0.003285) = 0.543 -> Nivel IV (E >= 0.80)
    requiere, nivel, eficiencia, radio = determine_spcr_level(nd=0.003285, nc=0.0015)
    assert requiere is True
    assert nivel == "Nivel IV"
    assert radio == 60.0


def test_check_point_coverage_rolling_sphere():
    """Test rolling sphere point protection check."""
    mast = {
        "id": "mast-1",
        "posicion_x": 10.0,
        "posicion_y": 10.0,
        "posicion_z": 0.0,
        "altura": 6.0,  # Tip at (10, 10, 6)
    }

    # Point directly under mast tip at height 5.0 -> Protected!
    prot, dist, mast_id = check_point_coverage_rolling_sphere(
        point=(10.0, 10.0, 5.0), masts=[mast], rolling_sphere_radius=30.0
    )
    assert prot is True
    assert mast_id == "mast-1"

    # Point 40m away horizontally (outside rolling sphere radius R=30m) -> Unprotected!
    prot_far, dist_far, _ = check_point_coverage_rolling_sphere(
        point=(50.0, 10.0, 5.0), masts=[mast], rolling_sphere_radius=30.0
    )
    assert prot_far is False
