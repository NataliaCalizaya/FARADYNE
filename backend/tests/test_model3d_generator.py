import pytest
from app.services.model3d_generator_service import (
    Model3DGeneratorService,
    top_plane,
    add_prism_with_roof,
)
from shapely.geometry import Point, Polygon


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


def test_uses_projected_side_points_for_slope():
    """La pendiente debe anclarse a los lados, no a la etiqueta del nivel."""
    from app.services.model3d_generator_service import prepare_region_levels

    region = {
        "niveles": [
            {"valor": 7.0, "x": 2.0, "y": 3.0, "punto_lado": {"x": 0.0, "y": 0.0}},
            {"valor": 8.0, "x": 8.0, "y": 3.0, "punto_lado": {"x": 10.0, "y": 0.0}},
        ]
    }

    prepared = prepare_region_levels(region)
    assert prepared["slope_pair"] == [
        {"value": 7.0, "x": 0.0, "y": 0.0},
        {"value": 8.0, "x": 10.0, "y": 0.0},
    ]


def test_concave_footprint_does_not_create_triangles_outside_2d_shape():
    footprint = [(0, 0), (4, 0), (4, 1), (1, 1), (1, 4), (0, 4)]
    prism = add_prism_with_roof({"id": "concava", "puntos": footprint})
    polygon = Polygon(footprint)
    top_faces = [face for face in prism["faces"] if face["type"] == "top"]

    assert len(top_faces) == 4
    for face in top_faces:
        centroid_x = sum(point[0] for point in face["points"]) / 3
        centroid_y = sum(point[1] for point in face["points"]) / 3
        assert polygon.covers(Point(centroid_x, centroid_y))


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
