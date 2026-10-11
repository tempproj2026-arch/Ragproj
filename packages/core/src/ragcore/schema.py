from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class Region(BaseModel):
    kind: str  # text, table, formula, figure
    bbox: List[float] # [x0, y0, x1, y1]
    image_path: str
    reading_order: int
    flags: Optional[Dict[str, Any]] = None

class Chunk(BaseModel):
    id: Optional[int] = None
    region_id: Optional[int] = None
    document_id: int
    page_number: int
    content_type: str
    content: str
    search_text: str
    section: Optional[str] = None
    embedding: Optional[List[float]] = None

class Figure(BaseModel):
    id: Optional[int] = None
    region_id: Optional[int] = None
    caption: Optional[str] = None
    description: Optional[str] = None
    image_path: str
    embedding: Optional[List[float]] = None
