"""Declaration of task kinds with the ``@task`` decorator."""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from lazy_bird.errors import InvalidInputError
from lazy_bird.priority import BACKGROUND

Resources = dict[str, float]

DEFAULT_PRIORITY = BACKGROUND  # lower numbers run first, see lazy_bird.priority


class TaskStop(BaseException):
    """Raised by ``ctx.checkpoint()`` to stop a task. Derives from BaseException so
    that a task's own ``except Exception`` blocks cannot swallow it."""


class TaskPaused(TaskStop):
    pass


class TaskCancelled(TaskStop):
    pass


class TaskInterrupted(TaskStop):
    """The server is shutting down, or a more urgent request needs the resources of this
    task: it goes back to the queue and resumes from its last checkpoint."""


@dataclass(frozen=True)
class TaskDefinition:
    kind: str
    function: Callable[..., Any]
    title: str
    resources: Resources | Callable[..., Resources]
    priority: int
    retries: int
    description: str
    engines: Callable[..., list[Any]] | None = None

    def engines_for(self, params: dict[str, Any]) -> list[Any]:
        """The engines this task will use (``ResolvedEngine``s), so their models can be made ready first."""
        return list(self.engines(**params)) if self.engines is not None else []

    def resources_for(self, params: dict[str, Any]) -> Resources:
        needs = self.resources(**params) if callable(self.resources) else self.resources
        return {name: float(amount) for name, amount in (needs or {}).items()}

    def title_for(self, params: dict[str, Any]) -> str:
        try:
            return self.title.format(**params)
        except (KeyError, IndexError, ValueError):
            return self.title

    def check_params(self, params: dict[str, Any]) -> None:
        try:
            inspect.signature(self.function).bind(None, **params)
            json.dumps(params)
        except TypeError as error:
            raise InvalidInputError(f"Invalid parameters for task '{self.kind}': {error}", code="invalid_task_params") from error

    def submit(
        self,
        *,
        title: str | None = None,
        priority: int | None = None,
        run_at: datetime | None = None,
        dedupe_key: str | None = None,
        resources: Resources | None = None,
        **params: Any,
    ):
        """Queue a run of this task; returns its ``TaskOut``.

        With ``dedupe_key``, an active (queued, running or paused) task with the same
        key is returned instead of creating a duplicate.
        """
        from lazy_bird.tasks import scheduler

        return scheduler().submit(
            self, params, title=title, priority=priority, run_at=run_at, dedupe_key=dedupe_key, resources=resources
        )

    def run(self, **params: Any) -> Any:
        """Run the task synchronously in the caller's thread, without the scheduler."""
        from lazy_bird.tasks.context import TaskContext

        self.check_params(params)
        return self.function(TaskContext.detached(params), **params)


_registry: dict[str, TaskDefinition] = {}


def task(
    kind: str,
    *,
    title: str | None = None,
    resources: Resources | Callable[..., Resources] | None = None,
    priority: int = DEFAULT_PRIORITY,
    retries: int = 0,
    engines: Callable[..., list[Any]] | None = None,
) -> Callable[[Callable[..., Any]], TaskDefinition]:
    """Declare a task kind.

    ``title`` may use the task parameters (``"Process file {file_id}"``).
    ``resources`` is a dict or a function of the parameters returning one.
    ``priority`` is how urgent the task is: the lower the number, the sooner it runs.
    ``retries`` is how many times a failed run is retried automatically.
    ``engines`` is a function of the parameters returning the resolved engines the task
    uses: the memory of their models is reserved before the task starts, not in
    ``resources``.
    """

    def decorator(function: Callable[..., Any]) -> TaskDefinition:
        existing = _registry.get(kind)
        if existing is not None and existing.function.__qualname__ != function.__qualname__:
            raise ValueError(f"Task kind '{kind}' is already declared by {existing.function.__module__}")
        definition = TaskDefinition(
            kind=kind,
            function=function,
            title=title or kind,
            resources=resources if resources is not None else {"cpu": 1},
            priority=priority,
            retries=retries,
            description=inspect.getdoc(function) or "",
            engines=engines,
        )
        _registry[kind] = definition
        return definition

    return decorator


def definition(kind: str) -> TaskDefinition | None:
    return _registry.get(kind)


def definitions() -> list[TaskDefinition]:
    return sorted(_registry.values(), key=lambda item: item.kind)


_listeners: list[Callable[[Any], None]] = []


def on_status_change(listener: Callable[[Any], None]) -> Callable[[Any], None]:
    """Call ``listener(task_out)`` whenever a task changes status (not on progress)."""
    if listener not in _listeners:
        _listeners.append(listener)
    return listener


def listeners() -> list[Callable[[Any], None]]:
    return list(_listeners)
