from app.services.niveles_utils import NivelesUtils


def test_keeps_detected_level_when_no_polygon_is_nearby():
    nivel = {"id": "n1", "valor": 7.9, "texto": "+7.90", "x": 100, "y": 100, "page": 0}

    niveles, descartados = NivelesUtils.asociar_niveles_automaticamente([], [nivel])

    assert niveles == [nivel]
    assert nivel["asociaciones"] == []
    assert nivel["asociado"] is False
    assert descartados[0]["motivo"] == "sin_poligono_cercano"
