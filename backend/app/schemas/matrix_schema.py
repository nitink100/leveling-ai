from pydantic import BaseModel, Field
from typing import List, Dict, Optional


class MatrixCell(BaseModel):
    text: str = Field(default="")

class MatrixRow(BaseModel):
    competency: str
    cells_by_level: Dict[str, MatrixCell]  # level_name -> cell

class ParsedCompetency(BaseModel):
    name: str
    cells: Dict[str, str] = Field(default_factory=dict)

class ParsedMatrix(BaseModel):
    confidence: float = 0.0
    role: Optional[str] = None
    levels: List[str] = Field(default_factory=list)
    competencies: List[ParsedCompetency] = Field(default_factory=list)
    notes: Optional[str] = None   # ✅ FIX
