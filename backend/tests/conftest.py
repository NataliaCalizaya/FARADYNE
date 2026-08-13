import pytest
from fastapi.testclient import TestClient
from main import app
from domain.model2d.model import Modelo2D
from uuid import uuid4

@pytest.fixture
def test_app():
    return TestClient(app)

@pytest.fixture
def test_db():
    pass

@pytest.fixture
def mock_modelo2d():
    return Modelo2D(project_id=uuid4(), source="manual", source_filename="test.dxf")

@pytest.fixture
def sample_dxf_path():
    return "test.dxf"
