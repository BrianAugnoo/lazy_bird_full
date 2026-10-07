from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ProcessingState = Literal["pending", "queued", "running", "paused", "done", "failed", "cancelled", "outdated", "unsupported"]
FileState = Literal["missing", "processing", "error", "outdated", "pending", "unsupported", "ready", "new"]


class ProcessingOut(BaseModel):
    """State of one processing (``processor`` + ``target``) of a file."""

    processor: str
    target: str
    state: ProcessingState
    content_hash: str | None = None
    task_id: int | None = None
    error: dict[str, Any] | None = None
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class FileOut(BaseModel):
    """A file with its processing states.

    ``state`` is a summary for display, derived from ``processing`` (which is the
    source of truth): missing > processing > error > outdated > pending >
    unsupported > ready; ``new`` when nothing was processed yet.
    """

    id: int
    name: str
    size: int
    extension: str
    path: str
    content_hash: str | None = None
    missing: bool = False
    chunk_count: int = 0
    state: FileState = "new"
    processing: list[ProcessingOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class FileContentIn(BaseModel):
    content: str


class FileUpdate(BaseModel):
    name: str | None = None
    dir: str | None = None


class ProcessRequest(BaseModel):
    """Run one processing of a file again, even if it is up to date."""

    processor: str
    target: str = ""
