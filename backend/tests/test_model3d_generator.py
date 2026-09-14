import pytest
from app.services.model3d_generator_service import (
    Model3DGeneratorService,
    top_plane,
    add_prism_with_roof,
)


def test_top_plane_sloped():
    """Test top_plane interpolation given a sloped pair."""
    region = {
        'levels': [7.05, 7.90],
        'slope_pair': [
            {'value': 7.05, 'x': 0.0, 'y': 0.0},
            {'value': 7.90, 'x': 10.0, 'y': 0.0},
        ]
    }
    zfun, zlow, zhigh = top_plane(region)
    assert zlow == 7.05
    assert zhigh == 7.90

    # At x=0, z should be 7.05
    assert pytest.approx(zfun(0.0, 0.0), 0.01) == 7.05
    # At x=10, z should be 7.90
    assert pytest.approx(zfun(10.0, 0.0), 0.01) == 7.90
    # Midpoint x=5, z should be 7.475
    assert pytest.approx(zfun(5.0, 0.0), 0.01) == 7.475


def test_generate_3d_mesh_from_2d():
    """Test 3D metadata generation from 2D regions."""
    modelo2d_sample = {
        "poligonos": [
            {
                "id": "R01",
                "footprint": [(0.0, 0.0), (20.0, 0.0), (20.0, 15.0), (0.0, 15.0)],
                "levels": [7.05, 7.90],
                "slope_pair": [
                    {"value": 7.05, "x": 0.0, "y": 0.0},
                    {"value": 7.90, "x": 20.0, "y": 0.0},
                ]
            }
        ],
        "cotas_altura": [
            {"texto": "+9.30", "valor": 9.30, "posicion": (10.0, 5.0)}
        ]
    }

    meta = Model3DGeneratorService.generate_3d_mesh_from_2d(modelo2d_sample)

    assert "bbox" in meta
    assert "regions" in meta
    assert "prisms" in meta
    assert meta["region_count"] == 1
    assert meta["tank"] is not None
    assert meta["tank"]["top"] == 9.30
