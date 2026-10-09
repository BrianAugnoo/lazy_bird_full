"""Background tasks: declare them with ``@task``, queue them with ``.submit()``.

Writing a task (the whole contract)::

    from lazy_bird.tasks import TaskContext, task

    @task("files.reindex", title="Reindex {folder}", resources={"cpu": 1})
    def reindex(ctx: TaskContext, folder: str) -> dict:
        done = ctx.state.get("done", 0)              # resume where the last checkpoint stopped
        items = list_items(folder)
        for index in range(done, len(items)):
            handle(items[index])
            ctx.checkpoint(progress=(index + 1) / len(items), state={"done": index + 1})
        return {"count": len(items)}                 # JSON-serializable result

    reindex.submit(folder="notes", priority=1)       # -> TaskOut (lower number = sooner)

- parameters are keyword arguments and must be JSON-serializable;
- ``resources`` (dict or function of the parameters) is what the run holds in the
  shared pool: ``cpu`` slots, ``vram_mb``, ``ram_mb``;
- ``engines`` (function of the parameters returning resolved engines) lists the local
  models the task uses: their memory is reserved before the task starts and not part
  of ``resources``; a more urgent request may make the task yield (it resumes later);
- ``ctx.checkpoint(...)`` is the only place where pause, cancel and shutdown stop a
  task; on resume the function runs again with ``ctx.state`` = last saved state;
- ``ctx.report(progress, message)`` shows progress without being a stop point.

Task modules live in ``tasks/{extension_name}/*.py`` (``default/`` ships with
lazy_bird, ``custom/`` is yours) and are imported at startup by ``discover_tasks``.
"""

from __future__ import annotations

from lazy_bird.extension.discovery import LoadFailure, import_module, iter_extension_modules, record_failures
from lazy_bird.preferences import task_preferences
from lazy_bird.tasks.context import TaskContext
from lazy_bird.tasks.memory import system_free
from lazy_bird.tasks.registry import TaskDefinition, definition, definitions, on_status_change, task
from lazy_bird.tasks.resources import ResourcePool, detect_capacity
from lazy_bird.tasks.scheduler import Scheduler

__all__ = ["TaskContext", "TaskDefinition", "definition", "definitions", "discover_tasks", "on_status_change", "publish", "scheduler", "task"]

_scheduler: Scheduler | None = None


def discover_tasks() -> list[str]:
    """Import every ``tasks/{extension_name}/*.py`` module; return the declared kinds."""
    failures = []
    for extension, module, import_path in iter_extension_modules(__name__):
        try:
            import_module(import_path)
        except Exception as error:
            failures.append(LoadFailure("task", import_path, str(error)))
    record_failures("task", failures)
    return [item.kind for item in definitions()]


def scheduler() -> Scheduler:
    """The process-wide scheduler, configured from the ``tasks`` preferences."""
    global _scheduler
    if _scheduler is None:
        settings = task_preferences()
        capacity = {**detect_capacity(), **settings["resources"]}
        _scheduler = Scheduler(ResourcePool(capacity, monitor=system_free), workers=settings["workers"])
    return _scheduler


def publish(event: dict) -> None:
    """Send an event to the task WebSocket clients (no-op before the scheduler exists)."""
    if _scheduler is not None:
        _scheduler.events.publish(event)


def start_scheduler() -> Scheduler:
    discover_tasks()
    current = scheduler()
    current.start()
    return current


def stop_scheduler() -> None:
    if _scheduler is not None:
        _scheduler.stop()
