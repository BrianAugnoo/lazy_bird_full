from pydantic import BaseModel, Field

from lazy_bird.schemas.chunk import ChunkOut


class SearchIn(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=100)
    preset_id: int | None = Field(default=None, description="Embedding preset; the default preset when omitted.")
    file_ids: list[int] | None = Field(default=None, description="Restrict the search to these files.")


class SearchResultOut(BaseModel):
    chunk: ChunkOut
    file_name: str
    file_path: str
    distance: float | None = None
