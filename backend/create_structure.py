import os

base_dir = r"c:\Users\natal\Documentos\FARADYNE\backend"

files_content = {
    "main.py": """from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.v1.router import api_router
from core.config import settings
import uvicorn

app = FastAPI(
    title=settings.APP_NAME,
    description="FARADYNE API for SPDA design",
    version=settings.APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

@app.on_event("startup")
async def startup_event():
    pass

@app.on_event("shutdown")
async def shutdown_event():
    pass

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == '__main__':
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
""",
    "requirements.txt": """fastapi>=0.110.0
uvicorn[standard]>=0.27.0
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
alembic>=1.13.0
python-multipart>=0.0.9
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
ezdxf>=1.2.0
shapely>=2.0.0
numpy>=1.26.0
scipy>=1.12.0
trimesh>=4.0.0
networkx>=3.2.0
apscheduler>=3.10.0
reportlab>=4.1.0
weasyprint>=62.0
jinja2>=3.1.0
matplotlib>=3.8.0
httpx>=0.27.0""",
    "requirements-dev.txt": """pytest>=8.0.0
pytest-asyncio>=0.23.0
pytest-cov>=5.0.0
httpx>=0.27.0
black>=24.0.0
ruff>=0.3.0
mypy>=1.9.0""",
    "pyproject.toml": """[tool.black]
line-length = 88
target-version = ['py311']

[tool.ruff]
line-length = 88
target-version = 'py311'

[tool.mypy]
python_version = "3.11"
strict = true

[tool.pytest.ini_options]
minversion = "8.0"
addopts = "-ra -q --cov"
testpaths = ["tests"]""",
    "api/v1/__init__.py": '"""API v1 Package"""',
    "api/v1/router.py": """from fastapi import APIRouter
from .endpoints import auth, projects, uploads, model2d, model3d, spda, reports, exports

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
api_router.include_router(model2d.router, prefix="/model2d", tags=["model2d"])
api_router.include_router(model3d.router, prefix="/model3d", tags=["model3d"])
api_router.include_router(spda.router, prefix="/spda", tags=["spda"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(exports.router, prefix="/exports", tags=["exports"])""",
    "api/v1/endpoints/__init__.py": '"""Endpoints Package"""',
    "api/v1/endpoints/auth.py": """from fastapi import APIRouter, HTTPException

router = APIRouter()

@router.post("/login")
async def login():
    raise HTTPException(status_code=501, detail="Auth not enabled yet")

@router.post("/register")
async def register():
    raise HTTPException(status_code=501, detail="Auth not enabled yet")""",
    "api/v1/endpoints/projects.py": """from fastapi import APIRouter, Depends
from uuid import UUID

router = APIRouter()

@router.get("/")
async def list_projects():
    return []

@router.post("/")
async def create_project():
    pass

@router.get("/{id}")
async def get_project(id: UUID):
    pass

@router.put("/{id}")
async def update_project(id: UUID):
    pass

@router.delete("/{id}")
async def delete_project(id: UUID):
    pass""",
    "api/v1/endpoints/uploads.py": """from fastapi import APIRouter, UploadFile, File, BackgroundTasks

router = APIRouter()

@router.post("/dxf")
async def upload_dxf(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    pass""",
    "api/v1/endpoints/model2d.py": """from fastapi import APIRouter
from uuid import UUID

router = APIRouter()

@router.get("/{project_id}")
async def get_model2d(project_id: UUID):
    pass""",
    "api/v1/endpoints/model3d.py": """from fastapi import APIRouter
from uuid import UUID

router = APIRouter()

@router.get("/{project_id}")
async def get_model3d(project_id: UUID):
    pass

@router.post("/{project_id}/generate")
async def generate_model3d(project_id: UUID):
    pass""",
    "api/v1/endpoints/spda.py": """from fastapi import APIRouter, HTTPException
from uuid import UUID

router = APIRouter()

@router.get("/{project_id}")
async def get_spda(project_id: UUID):
    raise HTTPException(status_code=501, detail="Not Implemented")""",
    "api/v1/endpoints/reports.py": """from fastapi import APIRouter, HTTPException
from uuid import UUID

router = APIRouter()

@router.post("/{project_id}")
async def generate_report(project_id: UUID):
    raise HTTPException(status_code=501, detail="Not Implemented")""",
    "api/v1/endpoints/exports.py": """from fastapi import APIRouter, HTTPException
from uuid import UUID

router = APIRouter()

@router.post("/{project_id}")
async def export_project(project_id: UUID):
    raise HTTPException(status_code=501, detail="Not Implemented")""",
    "api/v1/dependencies/__init__.py": '"""Dependencies Package"""',
    "api/v1/dependencies/auth.py": """def get_current_user():
    return None""",
    "api/v1/dependencies/database.py": """from database.session import SessionLocal

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()""",
    "core/__init__.py": '"""Core Package"""',
    "core/config.py": """from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    APP_NAME: str = 'FARADYNE'
    APP_VERSION: str = '0.1.0'
    DEBUG: bool = True
    DATABASE_URL: str = 'sqlite:///./test.db'
    SECRET_KEY: str = 'dev-secret-key-change-in-production'
    ALGORITHM: str = 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    UPLOAD_DIR: str = '/tmp/faradyne_uploads'
    MAX_FILE_SIZE_MB: int = 100
    ALLOWED_EXTENSIONS: List[str] = ['.dxf', '.dwg', '.pdf', '.png', '.jpg', '.jpeg']

settings = Settings()""",
    "core/exceptions.py": """class FaradyneException(Exception):
    pass

class ProjectNotFoundException(FaradyneException):
    pass

class Model2DNotFoundException(FaradyneException):
    pass

class InvalidFileFormatException(FaradyneException):
    pass

class ParseException(FaradyneException):
    pass

class GeometryException(FaradyneException):
    pass""",
    "core/logging.py": '"""Logging Setup"""',
    "core/events.py": '"""Events"""',
    "database/__init__.py": '"""Database Package"""',
    "database/session.py": """from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()""",
    "database/base.py": """from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

Base = declarative_base()

class BaseModel(Base):
    __abstract__ = True
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)""",
    "database/migrations/.gitkeep": "",
    "models/__init__.py": '"""Models Package"""',
    "models/user.py": """from database.base import BaseModel
from sqlalchemy import Column, String, Boolean

class User(BaseModel):
    __tablename__ = "users"
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)""",
    "models/project.py": """from database.base import BaseModel
from sqlalchemy import Column, String, Enum
import enum

class ProjectStatus(enum.Enum):
    DRAFT = "DRAFT"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"

class Project(BaseModel):
    __tablename__ = "projects"
    name = Column(String, index=True)
    description = Column(String, nullable=True)
    address = Column(String, nullable=True)
    status = Column(Enum(ProjectStatus), default=ProjectStatus.DRAFT)""",
    "models/model2d_record.py": """from database.base import BaseModel
from sqlalchemy import Column, String, Integer, Boolean, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

class Model2DRecord(BaseModel):
    __tablename__ = "model2d_records"
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"))
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    source = Column(String)
    source_filename = Column(String)
    model_data = Column(JSON)""",
    "models/model3d_record.py": """from database.base import BaseModel
class Model3DRecord(BaseModel):
    __tablename__ = "model3d_records"
    pass""",
    "models/audit_log.py": """from database.base import BaseModel
from sqlalchemy import Column, String, JSON
from sqlalchemy.dialects.postgresql import UUID

class AuditLog(BaseModel):
    __tablename__ = "audit_logs"
    entity_type = Column(String)
    entity_id = Column(UUID(as_uuid=True))
    action = Column(String)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    data = Column(JSON)""",
    "schemas/__init__.py": '"""Schemas Package"""',
    "schemas/auth.py": '"""Auth Schemas"""',
    "schemas/user.py": '"""User Schemas"""',
    "schemas/project.py": """from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from domain.project.entities import ProjectStatus

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    address: Optional[str] = None

class ProjectRead(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    address: Optional[str]
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None""",
    "schemas/upload.py": """from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class UploadResponse(BaseModel):
    file_id: str
    filename: str
    status: str
    model2d_id: Optional[UUID] = None
    message: str""",
    "schemas/model2d.py": """from pydantic import BaseModel
from domain.model2d.model import Modelo2D

class Model2DRead(BaseModel):
    model: Modelo2D""",
    "schemas/model3d.py": '"""Model3D Schemas"""',
    "schemas/common.py": """from pydantic import BaseModel
from typing import Generic, TypeVar, List, Optional

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    skip: int
    limit: int

class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None""",
    "domain/__init__.py": '"""Domain Package"""',
    "domain/model2d/__init__.py": '"""Model2D Domain Package"""',
    "domain/model2d/entities.py": """from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional, List, Dict
from uuid import UUID

class SemanticLayerType(Enum):
    WALLS = "WALLS"
    ROOF = "ROOF"
    FURNITURE = "FURNITURE"
    TEXT = "TEXT"
    DIMENSIONS = "DIMENSIONS"
    UNKNOWN = "UNKNOWN"

class EntityType(Enum):
    LINE = "LINE"
    POLYLINE = "POLYLINE"
    ARC = "ARC"
    CIRCLE = "CIRCLE"
    SPLINE = "SPLINE"
    TEXT = "TEXT"
    MTEXT = "MTEXT"
    INSERT = "INSERT"
    HATCH = "HATCH"

class Layer(BaseModel):
    id: str
    name: str
    color: str = "#FFFFFF"
    visible: bool = True
    locked: bool = False
    semantic_type: SemanticLayerType = SemanticLayerType.UNKNOWN

from .value_objects import Point

class Entity(BaseModel):
    id: UUID
    layer_id: str
    entity_type: EntityType
    geometry: dict
    attributes: dict = Field(default_factory=dict)

class Wall(BaseModel):
    id: UUID
    layer_id: str
    polyline: List[Point]
    thickness: Optional[float] = None

class Room(BaseModel):
    id: UUID
    name: Optional[str]
    polygon: List[Point]
    area: float = 0.0

class OpeningType(Enum):
    DOOR = "DOOR"
    WINDOW = "WINDOW"

class Opening(BaseModel):
    id: UUID
    opening_type: OpeningType
    position: Point
    width: float = 0.0

class RoofType(Enum):
    FLAT = "FLAT"
    PITCHED = "PITCHED"
    COMPLEX = "COMPLEX"

class Roof(BaseModel):
    polygon: List[Point]
    height: float
    roof_type: RoofType = RoofType.FLAT

class FloorHeight(BaseModel):
    floor_level: int
    floor_height: float
    ceiling_height: float""",
    "domain/model2d/value_objects.py": """from pydantic import BaseModel

class Point(BaseModel):
    x: float
    y: float
    z: float = 0.0

    class Config:
        frozen = True

class BoundingBox(BaseModel):
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min

    @property
    def area(self) -> float:
        return self.width * self.height

    class Config:
        frozen = True

class Height(BaseModel):
    value: float
    unit: str = 'm'

    class Config:
        frozen = True""",
    "domain/model2d/model.py": """from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Literal
from uuid import UUID, uuid4
from datetime import datetime
from .entities import Layer, Entity, Wall, Room, Opening, Roof, FloorHeight
from .value_objects import BoundingBox

class Modelo2D(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    source: Literal['dxf', 'dwg', 'pdf', 'image', 'manual']
    source_filename: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict = Field(default_factory=dict)
    bounding_box: Optional[BoundingBox] = None
    layers: List[Layer] = Field(default_factory=list)
    entities: List[Entity] = Field(default_factory=list)
    walls: List[Wall] = Field(default_factory=list)
    rooms: List[Room] = Field(default_factory=list)
    openings: List[Opening] = Field(default_factory=list)
    roof: Optional[Roof] = None
    heights: List[FloorHeight] = Field(default_factory=list)

    def get_layer_by_id(self, layer_id: str) -> Optional[Layer]:
        for layer in self.layers:
            if layer.id == layer_id:
                return layer
        return None

    def get_entities_by_layer(self, layer_id: str) -> List[Entity]:
        return [entity for entity in self.entities if entity.layer_id == layer_id]

    def get_visible_layers(self) -> List[Layer]:
        return [layer for layer in self.layers if layer.visible]""",
    "domain/model2d/repository.py": """from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID
from .model import Modelo2D

class IModel2DRepository(ABC):
    @abstractmethod
    def save(self, model: Modelo2D) -> Modelo2D:
        pass

    @abstractmethod
    def get_by_id(self, model_id: UUID) -> Optional[Modelo2D]:
        pass

    @abstractmethod
    def get_by_project_id(self, project_id: UUID) -> Optional[Modelo2D]:
        pass

    @abstractmethod
    def delete(self, model_id: UUID) -> bool:
        pass""",
    "domain/model3d/__init__.py": '"""Model3D Domain Package"""',
    "domain/model3d/entities.py": """from pydantic import BaseModel, Field
from enum import Enum
from typing import List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime
from domain.model2d.value_objects import Point

class MeshType(Enum):
    PRISM = "PRISM"
    COMPLEX = "COMPLEX"
    ROOF = "ROOF"

class Volume(BaseModel):
    id: UUID
    name: str
    mesh_data: Dict[str, Any]
    height: float
    base_polygon: List[Point]

class Modelo3D(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    model2d_id: UUID
    volumes: List[Volume] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)""",
    "domain/model3d/model.py": '"""Model3D Aggregate"""',
    "domain/model3d/repository.py": '"""Model3D Repository"""',
    "domain/project/__init__.py": '"""Project Domain Package"""',
    "domain/project/entities.py": """from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime

class ProjectStatus(Enum):
    DRAFT = "DRAFT"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"

class Project(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    description: Optional[str] = None
    address: Optional[str] = None
    status: ProjectStatus = ProjectStatus.DRAFT
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)""",
    "domain/project/repository.py": '"""Project Repository ABC"""',
    "domain/spda/__init__.py": '"""SPDA Domain Package"""',
    "domain/spda/entities.py": """from enum import Enum

class SPDALevel(Enum):
    I = "I"
    II = "II"
    III = "III"
    IV = "IV"

class Captor:
    \"\"\"Air termination network component.\"\"\"
    pass

class Conductor:
    \"\"\"Down conductor component.\"\"\"
    pass

class Bajada:
    \"\"\"Down conductor system.\"\"\"
    pass

class Malla:
    \"\"\"Earth termination system.\"\"\"
    pass""",
    "domain/spda/value_objects.py": """from pydantic import BaseModel
from .entities import SPDALevel

class NivelProteccion(BaseModel):
    level: SPDALevel
    rolling_sphere_radius: float

def get_radio_esfera(level: SPDALevel) -> float:
    if level == SPDALevel.I:
        return 20.0
    elif level == SPDALevel.II:
        return 30.0
    elif level == SPDALevel.III:
        return 45.0
    elif level == SPDALevel.IV:
        return 60.0
    return 60.0""",
    "domain/spda/repository.py": '"""SPDA Repository"""',
    "domain/user/__init__.py": '"""User Domain Package"""',
    "domain/user/entities.py": '"""User Entities"""',
    "domain/user/repository.py": '"""User Repository"""',
    "application/__init__.py": '"""Application Package"""',
    "application/cad/__init__.py": '"""CAD Application Use Cases"""',
    "application/cad/parse_dxf.py": """from uuid import UUID
from infrastructure.cad.parsers.dxf.dxf_parser import DXFParser
from infrastructure.cad.raw_model.raw_cad_data import RawCADData

class ParseDXFUseCase:
    def __init__(self):
        self.parser = DXFParser()

    def execute(self, file_path: str, project_id: UUID) -> RawCADData:
        return self.parser.parse(file_path)""",
    "application/cad/interpret_model.py": """from uuid import UUID
from infrastructure.cad.raw_model.raw_cad_data import RawCADData
from domain.model2d.model import Modelo2D

class InterpretCADModelUseCase:
    def execute(self, raw_data: RawCADData, project_id: UUID) -> Modelo2D:
        pass""",
    "application/cad/build_model2d.py": """from uuid import UUID
from fastapi import BackgroundTasks
from domain.model2d.model import Modelo2D

class BuildModel2DUseCase:
    def execute(self, file_path: str, project_id: UUID, background_tasks: BackgroundTasks | None = None) -> Modelo2D:
        pass""",
    "application/model3d/__init__.py": '"""Model3D Application Use Cases"""',
    "application/model3d/generate_model3d.py": '"""Generate Model3D Use Case"""',
    "application/project/__init__.py": '"""Project Application Use Cases"""',
    "application/project/create_project.py": """from schemas.project import ProjectCreate
from domain.project.entities import Project

class CreateProjectUseCase:
    def execute(self, data: ProjectCreate) -> Project:
        pass""",
    "application/project/get_project.py": """from uuid import UUID
from typing import Optional
from domain.project.entities import Project

class GetProjectUseCase:
    def execute(self, project_id: UUID) -> Optional[Project]:
        pass""",
    "application/project/list_projects.py": """from typing import List
from domain.project.entities import Project

class ListProjectsUseCase:
    def execute(self, skip: int = 0, limit: int = 20) -> List[Project]:
        pass""",
    "application/spda/__init__.py": '"""SPDA Application Use Cases"""',
    "application/spda/.gitkeep": "",
    "application/reports/__init__.py": '"""Reports Application Use Cases"""',
    "application/reports/generate_report.py": """from uuid import UUID

class GenerateReportUseCase:
    def execute(self, project_id: UUID, report_type: str) -> str:
        pass""",
    "infrastructure/__init__.py": '"""Infrastructure Package"""',
    "infrastructure/repositories/__init__.py": '"""Repositories Package"""',
    "infrastructure/repositories/project_repository.py": '"""Project Repository Impl"""',
    "infrastructure/repositories/model2d_repository.py": """from domain.model2d.repository import IModel2DRepository
from domain.model2d.model import Modelo2D
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional

class Model2DRepository(IModel2DRepository):
    def __init__(self, db: Session):
        self.db = db

    def save(self, model: Modelo2D) -> Modelo2D:
        pass

    def get_by_id(self, model_id: UUID) -> Optional[Modelo2D]:
        pass

    def get_by_project_id(self, project_id: UUID) -> Optional[Modelo2D]:
        pass

    def delete(self, model_id: UUID) -> bool:
        pass""",
    "infrastructure/repositories/model3d_repository.py": '"""Model3D Repository Impl"""',
    "infrastructure/repositories/user_repository.py": '"""User Repository Impl"""',
    "infrastructure/cad/__init__.py": '"""CAD Infrastructure Package"""',
    "infrastructure/cad/parsers/__init__.py": '"""Parsers Package"""',
    "infrastructure/cad/parsers/base_parser.py": """from abc import ABC, abstractmethod
from infrastructure.cad.raw_model.raw_cad_data import RawCADData

class BaseCADParser(ABC):
    @property
    @abstractmethod
    def format_name(self) -> str:
        pass

    @abstractmethod
    def parse(self, file_path: str) -> RawCADData:
        pass

    @abstractmethod
    def supports_format(self, extension: str) -> bool:
        pass""",
    "infrastructure/cad/parsers/dxf/__init__.py": '"""DXF Parsers Package"""',
    "infrastructure/cad/parsers/dxf/dxf_parser.py": """from infrastructure.cad.parsers.base_parser import BaseCADParser
from infrastructure.cad.raw_model.raw_cad_data import RawCADData

class DXFParser(BaseCADParser):
    @property
    def format_name(self) -> str:
        return 'dxf'

    def supports_format(self, extension: str) -> bool:
        return extension.lower() in ['.dxf']

    def parse(self, file_path: str) -> RawCADData:
        # TODO: Implement actual parsing using DXFLayerReader and DXFEntityReader
        pass""",
    "infrastructure/cad/parsers/dxf/dxf_layer_reader.py": """class DXFLayerReader:
    def read_layers(self, doc) -> list:
        # TODO: Return List[RawLayer]
        return []""",
    "infrastructure/cad/parsers/dxf/dxf_entity_reader.py": """class DXFEntityReader:
    def read_lines(self, doc) -> list: return []
    def read_polylines(self, doc) -> list: return []
    def read_arcs(self, doc) -> list: return []
    def read_circles(self, doc) -> list: return []
    def read_texts(self, doc) -> list: return []
    def read_mtexts(self, doc) -> list: return []
    def read_inserts(self, doc) -> list: return []
    def read_hatches(self, doc) -> list: return []
    def read_splines(self, doc) -> list: return []""",
    "infrastructure/cad/parsers/dxf/dxf_block_reader.py": """class DXFBlockReader:
    def read_blocks(self, doc) -> dict:
        return {}""",
    "infrastructure/cad/parsers/dwg/__init__.py": "",
    "infrastructure/cad/parsers/dwg/.gitkeep": "",
    "infrastructure/cad/parsers/ocr_image/__init__.py": "",
    "infrastructure/cad/parsers/ocr_image/.gitkeep": "",
    "infrastructure/cad/raw_model/__init__.py": '"""Raw CAD Data Model"""',
    "infrastructure/cad/raw_model/raw_entities.py": """from pydantic import BaseModel
from typing import List, Optional

class RawPoint(BaseModel):
    x: float
    y: float
    z: float = 0.0

class RawLine(BaseModel):
    start: RawPoint
    end: RawPoint
    layer: str
    color: Optional[int] = None

class RawPolyline(BaseModel):
    points: List[RawPoint]
    is_closed: bool
    layer: str
    color: Optional[int] = None

class RawArc(BaseModel):
    center: RawPoint
    radius: float
    start_angle: float
    end_angle: float
    layer: str

class RawCircle(BaseModel):
    center: RawPoint
    radius: float
    layer: str

class RawText(BaseModel):
    insert: RawPoint
    text: str
    height: float
    layer: str

class RawMText(BaseModel):
    insert: RawPoint
    text: str
    height: float
    layer: str

class RawInsert(BaseModel):
    name: str
    insert: RawPoint
    scale: RawPoint
    rotation: float
    layer: str

class RawHatch(BaseModel):
    paths: List[List[RawPoint]]
    layer: str

class RawSpline(BaseModel):
    control_points: List[RawPoint]
    degree: int
    layer: str""",
    "infrastructure/cad/raw_model/raw_cad_data.py": """from pydantic import BaseModel
from typing import List, Optional, Tuple
from .raw_entities import RawLine, RawPolyline, RawArc, RawCircle, RawText, RawMText, RawInsert, RawHatch, RawSpline

class RawLayer(BaseModel):
    id: str
    name: str
    color: int
    linetype: Optional[str] = None
    is_frozen: bool
    is_off: bool

class RawCADData(BaseModel):
    source_format: str
    source_filename: str
    dxf_version: Optional[str] = None
    units: str
    layers: List[RawLayer]
    lines: List[RawLine]
    polylines: List[RawPolyline]
    arcs: List[RawArc]
    circles: List[RawCircle]
    texts: List[RawText]
    mtexts: List[RawMText]
    inserts: List[RawInsert]
    hatches: List[RawHatch]
    splines: List[RawSpline]
    bounding_box: Optional[Tuple[float, float, float, float]] = None""",
    "infrastructure/cad/interpreter/__init__.py": '"""Interpreter Package"""',
    "infrastructure/cad/interpreter/base_interpreter.py": """from abc import ABC, abstractmethod
from infrastructure.cad.raw_model.raw_cad_data import RawCADData
from domain.model2d.model import Modelo2D

class BaseCADInterpreter(ABC):
    @abstractmethod
    def interpret(self, raw_data: RawCADData) -> Modelo2D:
        pass""",
    "infrastructure/cad/interpreter/layer_classifier.py": """from domain.model2d.entities import SemanticLayerType

class LayerClassifier:
    def classify(self, layer_name: str) -> SemanticLayerType:
        name_upper = layer_name.upper()
        if 'MURO' in name_upper or 'WALL' in name_upper or 'PARED' in name_upper:
            return SemanticLayerType.WALLS
        return SemanticLayerType.UNKNOWN""",
    "infrastructure/cad/interpreter/wall_detector.py": """from typing import List
from domain.model2d.entities import Wall

class WallDetector:
    def detect(self, entities, layer_type_map) -> List[Wall]:
        raise NotImplementedError('Wall detection will be implemented in a future iteration')""",
    "infrastructure/cad/interpreter/room_detector.py": """class RoomDetector:
    pass""",
    "infrastructure/cad/interpreter/roof_detector.py": """class RoofDetector:
    pass""",
    "infrastructure/cad/interpreter/opening_detector.py": """class OpeningDetector:
    pass""",
    "infrastructure/cad/interpreter/perimeter_detector.py": """class PerimeterDetector:
    pass""",
    "infrastructure/cad/normalizer/__init__.py": '"""Normalizer Package"""',
    "infrastructure/cad/normalizer/entity_normalizer.py": """from infrastructure.cad.raw_model.raw_cad_data import RawCADData
from domain.model2d.entities import Entity

class EntityNormalizer:
    def normalize(self, raw_data: RawCADData) -> list[Entity]:
        # TODO: Implement mapping
        return []""",
    "infrastructure/cad/normalizer/coordinate_transformer.py": """from domain.model2d.value_objects import Point, BoundingBox
from typing import List

class CoordinateTransformer:
    def transform(self, points: List[Point], translation, scale, rotation) -> List[Point]:
        pass

    def calculate_bounding_box(self, points: List[Point]) -> BoundingBox:
        pass

    def center_to_origin(self, points: List[Point]) -> List[Point]:
        pass""",
    "infrastructure/geometry/__init__.py": '"""Geometry Package"""',
    "infrastructure/geometry/polygon_ops.py": """from domain.model2d.value_objects import Point
from typing import List

def close_polygon(points: List[Point]) -> List[Point]:
    pass

def join_segments(segments: List[tuple]) -> List[List[Point]]:
    pass

def simplify_polygon(points: List[Point], tolerance: float) -> List[Point]:
    pass

def merge_polygons(polygons: list) -> object:
    pass""",
    "infrastructure/geometry/offset_ops.py": """def offset_polygon(polygon, distance: float) -> object:
    pass

def buffer_polygon(polygon, distance: float) -> object:
    pass""",
    "infrastructure/geometry/area_ops.py": """def calculate_area(polygon) -> float:
    pass

def calculate_perimeter(polygon) -> float:
    pass""",
    "infrastructure/geometry/intersection_ops.py": """def intersect(geom1, geom2) -> object:
    pass

def union(geom1, geom2) -> object:
    pass

def difference(geom1, geom2) -> object:
    pass

def do_intersect(geom1, geom2) -> bool:
    pass""",
    "infrastructure/geometry/triangulation.py": """from domain.model2d.value_objects import Point
from typing import List, Tuple

def triangulate(points: List[Point]) -> List[Tuple]:
    # TODO: Uses scipy.spatial.Delaunay
    pass""",
    "infrastructure/geometry/graph_ops.py": """import networkx as nx

def build_connectivity_graph(entities: list) -> nx.Graph:
    pass

def find_cycles(graph: nx.Graph) -> list:
    pass

def find_enclosed_regions(graph: nx.Graph) -> list:
    pass""",
    "infrastructure/model3d/__init__.py": '"""Model3D Infrastructure Package"""',
    "infrastructure/model3d/extruder.py": """from domain.model2d.value_objects import Point
from domain.model3d.entities import Volume
from typing import List

class Extruder:
    def extrude(self, polygon: List[Point], height: float) -> Volume:
        # TODO
        pass""",
    "infrastructure/model3d/mesh_builder.py": """from domain.model3d.entities import Volume

class MeshBuilder:
    def build_mesh(self, volume: Volume) -> dict:
        # TODO: using trimesh
        pass""",
    "infrastructure/model3d/scene_builder.py": """from domain.model3d.entities import Modelo3D

class SceneBuilder:
    def build_scene(self, model3d: Modelo3D) -> dict:
        # TODO: using pyvista
        pass""",
    "infrastructure/security/__init__.py": '"""Security Package"""',
    "infrastructure/security/jwt_handler.py": """class JWTHandler:
    def create_access_token(self, data: dict) -> str:
        # TODO
        pass

    def verify_token(self, token: str) -> dict | None:
        # TODO
        pass""",
    "infrastructure/security/password_hasher.py": """class PasswordHasher:
    def hash_password(self, plain: str) -> str:
        # TODO: will use passlib
        pass

    def verify_password(self, plain: str, hashed: str) -> bool:
        # TODO
        pass""",
    "infrastructure/security/auth_service.py": """class AuthService:
    def authenticate(self, username, password, db):
        # TODO
        pass""",
    "infrastructure/reports/__init__.py": '"""Reports Infrastructure Package"""',
    "infrastructure/reports/templates/__init__.py": "",
    "infrastructure/reports/templates/memoria_descriptiva.html": "<html><body><h1>Memoria Descriptiva</h1><p>{{ project.name }}</p><p>{{ model2d.metadata }}</p></body></html>",
    "infrastructure/reports/templates/listado_materiales.html": "<html><body><h1>Listado de Materiales</h1><p>{{ project.name }}</p></body></html>",
    "infrastructure/reports/pdf_generator.py": """class PDFGenerator:
    def generate(self, template_name: str, context: dict, output_path: str) -> str:
        # TODO: Use WeasyPrint/ReportLab
        pass""",
    "infrastructure/reports/report_builder.py": """class ReportBuilder:
    def build_memoria_descriptiva(self, project, model2d) -> str:
        pass

    def build_listado_materiales(self, project, spda_config) -> str:
        pass""",
    "infrastructure/exports/__init__.py": '"""Exports Infrastructure Package"""',
    "infrastructure/exports/dxf_exporter.py": """from domain.model2d.model import Modelo2D

class DXFExporter:
    def export(self, model2d: Modelo2D, output_path: str) -> str:
        # TODO
        pass""",
    "infrastructure/exports/pdf_exporter.py": """from domain.model2d.model import Modelo2D

class PDFExporter:
    def export(self, model2d: Modelo2D, output_path: str) -> str:
        # TODO
        pass""",
    "infrastructure/exports/png_exporter.py": """from domain.model2d.model import Modelo2D

class PNGExporter:
    def export(self, model2d: Modelo2D, output_path: str, dpi: int = 150) -> str:
        # TODO
        pass""",
    "infrastructure/exports/dwg_exporter.py": """from domain.model2d.model import Modelo2D

class DWGExporter:
    def export(self, model2d: Modelo2D, output_path: str) -> str:
        # TODO
        pass""",
    "tasks/__init__.py": '"""Tasks Package"""',
    "tasks/scheduler.py": """from apscheduler.schedulers.background import BackgroundScheduler
from .cleanup import cleanup_temp_files

scheduler = BackgroundScheduler()
scheduler.add_job(cleanup_temp_files, 'cron', hour=2)

def dummy_version_job():
    pass

scheduler.add_job(dummy_version_job, 'cron', hour=3)

def start():
    scheduler.start()

def shutdown():
    scheduler.shutdown()""",
    "tasks/cleanup.py": """from core.config import settings
import os
import time

def cleanup_temp_files():
    now = time.time()
    for filename in os.listdir(settings.UPLOAD_DIR):
        filepath = os.path.join(settings.UPLOAD_DIR, filename)
        if os.stat(filepath).st_mtime < now - 24 * 3600:
            if os.path.isfile(filepath):
                os.remove(filepath)""",
    "tests/__init__.py": '"""Tests Package"""',
    "tests/conftest.py": """import pytest
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
    return "test.dxf\"""",
    "tests/unit/__init__.py": '"""Unit Tests Package"""',
    "tests/unit/domain/__init__.py": '"""Domain Tests Package"""',
    "tests/unit/domain/test_model2d.py": """from domain.model2d.model import Modelo2D
from uuid import uuid4

def test_create_empty_model2d():
    model = Modelo2D(project_id=uuid4(), source="manual", source_filename="test")
    assert model.source == "manual"

def test_get_visible_layers():
    pass

def test_get_entities_by_layer():
    pass

def test_bounding_box_properties():
    pass""",
    "tests/unit/domain/test_model3d.py": '"""Model3D Tests"""',
    "tests/unit/infrastructure/__init__.py": '"""Infrastructure Tests Package"""',
    "tests/unit/infrastructure/cad/__init__.py": '"""CAD Infrastructure Tests"""',
    "tests/unit/infrastructure/cad/test_dxf_parser.py": """from infrastructure.cad.parsers.dxf.dxf_parser import DXFParser

def test_dxf_parser_supports_format():
    parser = DXFParser()
    assert parser.supports_format(".dxf") == True

def test_dxf_parser_rejects_unsupported_format():
    parser = DXFParser()
    assert parser.supports_format(".dwg") == False

def test_parse_returns_raw_cad_data_type():
    pass""",
    "tests/unit/infrastructure/cad/test_entity_normalizer.py": '"""Entity Normalizer Tests"""',
    "tests/unit/infrastructure/geometry/__init__.py": '"""Geometry Infrastructure Tests"""',
    "tests/unit/infrastructure/geometry/test_polygon_ops.py": """def test_close_polygon_already_closed():
    pass

def test_close_polygon_opens():
    pass""",
    "tests/unit/infrastructure/geometry/test_triangulation.py": '"""Triangulation Tests"""',
    "tests/unit/application/__init__.py": '"""Application Tests Package"""',
    "tests/unit/application/test_parse_dxf.py": '"""Parse DXF Use Case Tests"""',
    "tests/integration/__init__.py": '"""Integration Tests Package"""',
    "tests/integration/test_dxf_pipeline.py": """import pytest

@pytest.mark.skip(reason="No real DXF file")
def test_full_pipeline_returns_model2d():
    pass""",
    "tests/integration/test_api_projects.py": """def test_create_project(test_app):
    pass

def test_get_project_not_found(test_app):
    pass

def test_list_projects_empty(test_app):
    pass""",
    "tests/fixtures/__init__.py": "",
    "tests/fixtures/README.md": "# Test Fixtures\nPlace your test files here.",
}

import os

for path, content in files_content.items():
    full_path = os.path.join(base_dir, path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content)
