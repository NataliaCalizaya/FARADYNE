from domain.model2d.model import Modelo2D
from uuid import uuid4

def test_create_empty_model2d():
    model = Modelo2D(project_id=uuid4(), source="manual", source_filename="test")
    assert model.source == "manual"

def test_get_visible_layers():
    pass

def test_get_entities_by_layer():
    pass

def test_bounding_box_properties():
    pass
