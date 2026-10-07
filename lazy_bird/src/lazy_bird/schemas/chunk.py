from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import to_jsonable_python

from lazy_bird.schemas.types import UtcDatetime


class ChunkIn(BaseModel):
    """A chunk as returned by a chunker extension (``chunk(file, max_token)``)."""

    content: str
    start_line: int
    end_line: int
    start_row: int | None = None
    end_row: int | None = None
    token_count: int | None = None
    meta: dict[str, Any] = Field(default_factory=dict)

    @field_validator("meta")
    @classmethod
    def _json_safe(cls, value: dict[str, Any]) -> dict[str, Any]:
        # Front matter may hold dates or other values JSON cannot store as is.
        return to_jsonable_python(value, fallback=str)


class ChunkOut(ChunkIn):
    id: int
    file_id: int
    position: int
    created_at: UtcDatetime
    model_config = ConfigDict(from_attributes=True)
