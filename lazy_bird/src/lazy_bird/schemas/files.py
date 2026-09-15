from pydantic import BaseModel, ConfigDict

class FileOut(BaseModel):
    id: int
    name: str
    size: int
    extension: str
    path: str
    status: str

    model_config = ConfigDict(from_attributes=True)


class FileContentIn(BaseModel):
    content: str


class FileUpdate(BaseModel):
    name: str | None = None
    dir: str | None = None
