from typing import Any, Literal
from pydantic import BaseModel, Field

class DatabaseSelectionIn(BaseModel):
    kind: Literal["sql", "vector"]
    name: str = Field(min_length=1)
    settings: dict[str, Any] = Field(default_factory=dict)

class DatabaseDisconnectIn(BaseModel):
    kind: Literal["sql", "vector"]
    name: str
    drop: bool = False


class SelectedDatabaseOut(BaseModel):
    sql: str
    vector: str


class VectorTableOut(BaseModel):
    model_name: str
    vectors: int
