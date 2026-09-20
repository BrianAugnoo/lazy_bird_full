from sqlalchemy import CheckConstraint, Column, JSON
from sqlmodel import SQLModel, Field

class InferenceEngine(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    file_path: str
    kwargs: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    kwargs_keys: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    
class SelectedInferenceEngine(SQLModel, table=True):
    __table_args__ = (CheckConstraint("id = 1", name="selected_inference_engine_id_is_one"),)
    id: int = Field(default=1, primary_key=True)
    inference_engine_id: int = Field(foreign_key="inferenceengine.id", nullable=False)