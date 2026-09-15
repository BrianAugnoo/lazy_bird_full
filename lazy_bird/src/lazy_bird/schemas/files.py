from pydantic import BaseModel, ConfigDict

class FileOut(BaseModel):
    name: str
    size: int
    extension: str
    path: str
    status: str

    model_config = ConfigDict(from_attributes=True)
