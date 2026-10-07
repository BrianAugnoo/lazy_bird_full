from datetime import datetime, timezone

from sqlalchemy import Column, JSON, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


class Chunk(SQLModel, table=True):
    """A piece of a file produced by the chunker; vectors reference it by ``id``."""

    __table_args__ = (UniqueConstraint("file_id", "position", name="uq_chunk_file_position"),)

    id: int | None = Field(default=None, primary_key=True)
    file_id: int = Field(foreign_key="file.id", nullable=False, index=True, ondelete="CASCADE")
    position: int = Field(nullable=False)
    content: str = Field(sa_column=Column(Text, nullable=False))
    start_line: int
    end_line: int
    start_row: int | None = None
    end_row: int | None = None
    token_count: int | None = None
    meta: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
