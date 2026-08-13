from pydantic import BaseModel
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
    bounding_box: Optional[Tuple[float, float, float, float]] = None
