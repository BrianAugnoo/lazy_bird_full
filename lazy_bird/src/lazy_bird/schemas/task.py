from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

TaskStatus = Literal["queued", "running", "paused", "completed", "failed", "cancelled"]


class TaskOut(BaseModel):
    """A task as shown to clients.

    ``control`` is a pending request on a running task ("pause" or "cancel"), applied
    at its next checkpoint. ``waiting_for`` lists what keeps a queued task from
    starting (resource names, "worker" or "schedule").
    """

    id: int
    kind: str
    title: str
    params: dict[str, Any]
    status: TaskStatus
    control: str | None = None
    priority: int
    position: int
    run_at: datetime | None = None
    resources: dict[str, float]
    progress: float | None = None
    message: str | None = None
    result: Any = None
    error: dict[str, Any] | None = None
    attempts: int
    max_attempts: int
    dedupe_key: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    waiting_for: list[str] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class TaskUpdate(BaseModel):
    priority: int | None = None
    run_at: datetime | None = None


class TaskMove(BaseModel):
    """Move a queued or paused task just before or just after another one."""

    before_id: int | None = None
    after_id: int | None = None


class TaskKindOut(BaseModel):
    kind: str
    title: str
    description: str
    priority: int
    retries: int
