from datetime import datetime, timezone
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Embedded(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("file_id", "llm_model_id", name="uq_embedded_file_model"),)
    id: int | None = Field(default=None, primary_key=True)
    file_id: int = Field(foreign_key="file.id", nullable=False)
    llm_model_id: int = Field(foreign_key="llmmodel.id", nullable=False)
    status: str = Field(default="pending", nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)


class EmbeddedVectorDatabase(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("embedded_id", "vector_database_id", name="uq_embedded_vector_database"),)
    id: int | None = Field(default=None, primary_key=True)
    embedded_id: int = Field(foreign_key="embedded.id", nullable=False)
    vector_database_id: int = Field(foreign_key="vectordatabase.id", nullable=False)
