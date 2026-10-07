from pydantic import BaseModel, ConfigDict, Field


class APIKeyIn(BaseModel):
    name: str = Field(min_length=1)
    key: str = Field(min_length=1)

    model_config = ConfigDict(from_attributes=True)


class APIKeyUpdate(BaseModel):
    key: str = Field(min_length=1)


class APIKeyOut(BaseModel):
    name: str

    model_config = ConfigDict(from_attributes=True)
