from sqlalchemy import CheckConstraint, Column, JSON
from sqlmodel import SQLModel, Field


class EmbeddingEngine(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    file_path: str
    formats: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    kwargs: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class SelectedEmbeddingEngine(SQLModel, table=True):
    __table_args__ = (CheckConstraint("id = 1", name="selected_embedding_engine_id_is_one"),)
    id: int = Field(default=1, primary_key=True)
    embedding_engine_id: int = Field(foreign_key="embeddingengine.id", nullable=False)
