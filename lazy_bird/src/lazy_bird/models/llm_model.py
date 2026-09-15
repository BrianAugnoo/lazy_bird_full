from sqlalchemy import Column, JSON
from sqlmodel import SQLModel, Field

class LLMModel(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    hf_path: str
    local_path: str
    dimension: int
    max_context_length: int | None = Field(default=None)
    selected_context: int | None = Field(default=None)
    formats: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    selected_format: str | None = Field(default=None)
