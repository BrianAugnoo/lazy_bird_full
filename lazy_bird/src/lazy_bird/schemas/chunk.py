from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChunkIn(BaseModel):
    """A chunk as returned by a chunker extension (``Chunck(file, max_token)``)."""

    content: str
    start_line: int
    end_line: int
    start_row: int | None = None
    end_row: int | None = None
    token_count: int | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class ChunkOut(ChunkIn):
    id: int
    file_id: int
    position: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
