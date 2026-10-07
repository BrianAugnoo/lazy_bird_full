"""The object a task function receives as first argument."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from lazy_bird.tasks.registry import TaskCancelled, TaskInterrupted, TaskPaused

if TYPE_CHECKING:
    from lazy_bird.tasks.scheduler import Scheduler

REPORT_INTERVAL_SECONDS = 0.25


class TaskContext:
    """Progress reporting and cooperative stop points of a running task.

    - ``ctx.params``: the task parameters (also passed as keyword arguments);
    - ``ctx.state``: the state saved by the last checkpoint, ``{}`` on a fresh run;
    - ``ctx.report(progress, message)``: show progress (0..1), never stops the task;
    - ``ctx.checkpoint(progress, message, state)``: show progress, save ``state``, and
      stop here (raising) if a pause, cancellation or shutdown was requested.

    Contract: when a paused or interrupted task resumes, its function is called again
    from the start with ``ctx.state`` set to the last saved state. Work done before
    the last checkpoint must therefore be skipped using that state (or be safe to redo).
    """

    def __init__(self, task_id: int | None, params: dict[str, Any], state: dict[str, Any], scheduler: Scheduler | None) -> None:
        self.task_id = task_id
        self.params = dict(params)
        self.state = dict(state)
        self._scheduler = scheduler
        self._last_report = 0.0

    @classmethod
    def detached(cls, params: dict[str, Any]) -> "TaskContext":
        """A context for running a task inline: reports are ignored and it never stops."""
        return cls(None, params, {}, None)

    def report(self, progress: float | None = None, message: str | None = None) -> None:
        now = time.monotonic()
        if self._scheduler is None or now - self._last_report < REPORT_INTERVAL_SECONDS:
            return
        self._last_report = now
        self._scheduler.record_progress(self.task_id, progress, message, None)

    def checkpoint(self, progress: float | None = None, message: str | None = None, state: dict[str, Any] | None = None) -> None:
        if state is not None:
            self.state = dict(state)
        if self._scheduler is None:
            return
        self._last_report = time.monotonic()
        self._scheduler.record_progress(self.task_id, progress, message, self.state if state is not None else None)
        control = self._scheduler.control_of(self.task_id)
        if control == "pause":
            raise TaskPaused()
        if control == "cancel":
            raise TaskCancelled()
        if control == "interrupt":
            raise TaskInterrupted()
