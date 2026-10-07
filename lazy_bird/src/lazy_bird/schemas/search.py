from typing import Any
from pydantic import BaseModel, Field

class SearchIn(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=100)
    preset_id: int | None = Field(default=None, description="Embedding preset; the default preset when omitted.")

class ChunkOut(BaseModel):
    content: str
    start_line: int
    end_line: int
    start_row: int | None = None
    end_row: int | None = None
    meta_data: dict[str, Any]
    embedded_id: int
    distance: float | None = None
