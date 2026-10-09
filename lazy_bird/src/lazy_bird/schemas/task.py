from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from lazy_bird.schemas.types import UtcDatetime

TaskStatus = Literal["queued", "running", "paused", "completed", "failed", "cancelled"]


class TaskOut(BaseModel):
    """A task as shown to clients.

    ``control`` is a pending request on a running task ("pause" or "cancel"), applied
    at its next checkpoint. ``waiting_for`` lists what keeps a queued task from
    starting (resource names, "worker" or "schedule"). ``priority``: the lower the
    number, the sooner the task runs (5 by default, 0 = run now).
    """

    id: int
    kind: str
    title: str
    params: dict[str, Any]
    status: TaskStatus
    control: str | None = None
    priority: int
    position: int
    run_at: UtcDatetime | None = None
    resources: dict[str, float]
    progress: float | None = None
    message: str | None = None
    result: Any = None
    error: dict[str, Any] | None = None
    attempts: int
    max_attempts: int
    dedupe_key: str | None = None
    created_at: UtcDatetime
    updated_at: UtcDatetime
    started_at: UtcDatetime | None = None
    finished_at: UtcDatetime | None = None
    waiting_for: list[str] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class TaskUpdate(BaseModel):
    priority: int | None = None
    run_at: UtcDatetime | None = None


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
