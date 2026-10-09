"""The object a task function receives as first argument."""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Any, Callable, TypeVar

from lazy_bird.tasks.registry import TaskCancelled, TaskInterrupted, TaskPaused

if TYPE_CHECKING:
    from lazy_bird.tasks.scheduler import Scheduler

REPORT_INTERVAL_SECONDS = 0.25
BLOCKING_POLL_SECONDS = 0.5

T = TypeVar("T")


class TaskContext:
    """Progress reporting and cooperative stop points of a running task.

    - ``ctx.params``: the task parameters (also passed as keyword arguments);
    - ``ctx.state``: the state saved by the last checkpoint, ``{}`` on a fresh run;
    - ``ctx.report(progress, message)``: show progress (0..1), never stops the task;
    - ``ctx.checkpoint(progress, message, state)``: show progress, save ``state``, and
      stop here (raising) if a pause, cancellation or shutdown was requested;
    - ``ctx.run_blocking(function, *args)``: a call that cannot reach a checkpoint (a
      download), during which the task can still be stopped.

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
        self._stop_if_asked()

    def run_blocking(self, function: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Run ``function`` in a thread and wait for it, stopping (raising) as soon as a pause,
        cancellation or shutdown is requested, like a checkpoint would.

        The call itself cannot be stopped: it goes on in its thread. Only an isolated task
        really ends it, since its process ends with its run; so use it in isolated kinds.
        """
        if self._scheduler is None:
            return function(*args, **kwargs)
        outcome: dict[str, Any] = {}

        def target() -> None:
            try:
                outcome["value"] = function(*args, **kwargs)
            except BaseException as error:
                outcome["error"] = error

        thread = threading.Thread(target=target, name=f"task-{self.task_id}-blocking", daemon=True)
        thread.start()
        while thread.is_alive():
            thread.join(BLOCKING_POLL_SECONDS)
            if thread.is_alive():
                self._stop_if_asked()
        if "error" in outcome:
            raise outcome["error"]
        return outcome["value"]

    def _stop_if_asked(self) -> None:
        control = self._scheduler.control_of(self.task_id)
        if control == "pause":
            raise TaskPaused()
        if control == "cancel":
            raise TaskCancelled()
        if control == "interrupt":
            raise TaskInterrupted()
