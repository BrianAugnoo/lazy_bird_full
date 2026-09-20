from pydantic import BaseModel, ConfigDict

class APIKeyIn(BaseModel):
    name: str
    key: str

    model_config = ConfigDict(from_attributes=True)

class APIKeyOut(BaseModel):
    name: str

    model_config = ConfigDict(from_attributes=True)