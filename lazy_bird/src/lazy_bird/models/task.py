from datetime import datetime, timezone

from sqlalchemy import Column, Index, JSON, text
from sqlmodel import Field, SQLModel

ACTIVE_STATUSES = ("queued", "running", "paused")
TERMINAL_STATUSES = ("completed", "failed", "cancelled")


class Task(SQLModel, table=True):
    """A unit of background work executed by the scheduler (see ``lazy_bird.tasks``)."""

    __table_args__ = (
        Index(
            "uq_task_active_dedupe_key",
            "dedupe_key",
            unique=True,
            sqlite_where=text("status IN ('queued', 'running', 'paused')"),
            postgresql_where=text("status IN ('queued', 'running', 'paused')"),
        ),
        Index("ix_task_queue_order", "status", "priority", "position"),
        Index("ix_task_status_position", "status", "position"),
        Index("ix_task_status_finished", "status", "finished_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    kind: str = Field(index=True)
    title: str
    params: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="queued")
    control: str | None = Field(default=None)
    priority: int = Field(default=5)
    position: int = Field(default=0)
    run_at: datetime | None = Field(default=None)
    resources: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    progress: float | None = Field(default=None)
    message: str | None = Field(default=None)
    state: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    result: dict | list | str | int | float | bool | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    error: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    attempts: int = Field(default=0)
    max_attempts: int = Field(default=1)
    dedupe_key: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    started_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)
