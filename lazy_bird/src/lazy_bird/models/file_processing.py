from datetime import datetime, timezone

from sqlalchemy import Column, Index, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


class FileProcessing(SQLModel, table=True):
    """State of one processing type applied to one file.

    ``processor`` names the kind of processing ("chunking", "embedding"...),
    ``target`` distinguishes several results of the same kind (for embedding, the
    model the vectors come from). See ``crud/file_processing.py`` for the states.
    """

    __table_args__ = (
        UniqueConstraint("file_id", "processor", "target", name="uq_file_processing"),
        Index("ix_fileprocessing_processor_target", "processor", "target"),
    )

    id: int | None = Field(default=None, primary_key=True)
    file_id: int = Field(foreign_key="file.id", nullable=False, index=True, ondelete="CASCADE")
    processor: str
    target: str = Field(default="")
    state: str = Field(default="pending")
    # File hash the result was (or is being) computed from.
    content_hash: str | None = Field(default=None)
    task_id: int | None = Field(default=None, foreign_key="task.id", ondelete="SET NULL", index=True)
    error: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
