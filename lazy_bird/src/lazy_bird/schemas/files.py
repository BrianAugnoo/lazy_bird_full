from pydantic import BaseModel, ConfigDict, Field

class FileOut(BaseModel):
    id: int
    name: str
    size: int
    extension: str
    path: str
    status: str
    embedded_by: list[int] = Field(default_factory=list)
    vector_db: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class FileContentIn(BaseModel):
    content: str


class FileUpdate(BaseModel):
    name: str | None = None
    dir: str | None = None
