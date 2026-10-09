"""Isolated tasks: a task kind declared with ``isolated=True`` runs in a process of its own.

Why: a task that never reaches a checkpoint cannot be stopped in a thread, and a heavy one
(large dataset work...) that crashes or exhausts memory takes the server down with it. In a
process it can be killed, and its memory comes back.

The server's worker thread stays in charge of the run (``TaskHost.run``): it starts
``python -m lazy_bird.task_host`` (see ``processes``), sends it the task, then serves it
until the run ends:

- ``("progress", progress, message, state)`` -> recorded like any task's progress
  (``state`` is a checkpoint);
- ``("control",)`` -> answered with the pending control ("pause", "cancel", "interrupt" or None);
- ``("engine", kind, engine_id, settings, preset_id, operation, args)`` -> run on the server,
  whose residency holds the models (the task's reservations, the memory accounting and the
  model processes stay there); answered ``("ok", value)`` or ``("error", payload)``;
- ``("done", result, state)``, ``("stopped", "paused" | "cancelled" | "interrupted", state)``
  or ``("failed", payload, state)`` ends the run.

The child attaches to the server's databases (nothing is migrated), reads the same preference
file, loads the same engine modules (without registering them) and imports the module that
declares the task kind. Engines that are not local (APIs) are called from the child itself.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator

from loguru import logger

from lazy_bird.processes import ChildProcess, ProcessFailed, connect_to_parent, error_payload
from lazy_bird.tasks.registry import TaskCancelled, TaskInterrupted, TaskPaused

if TYPE_CHECKING:
    from lazy_bird.crud.engine import ResolvedEngine
    from lazy_bird.schemas.task import TaskOut
    from lazy_bird.tasks.context import TaskContext
    from lazy_bird.tasks.registry import TaskDefinition
    from lazy_bird.tasks.scheduler import Scheduler

STOPS = {"pause": TaskPaused, "paused": TaskPaused, "cancel": TaskCancelled, "cancelled": TaskCancelled, "interrupt": TaskInterrupted, "interrupted": TaskInterrupted}


class TaskProcessError(ProcessFailed):
    """An isolated task failed in its process, or its process stopped unexpectedly."""

    code = "task_failed"


def _remote_error(payload: dict[str, Any]) -> TaskProcessError:
    details = {**payload.get("details", {}), "type": payload["type"], "traceback": payload["traceback"]}
    return TaskProcessError(payload["message"], code=payload.get("code", "task_failed"), details=details)


# ----------------------------------------------------------------- server side
class TaskHost:
    """The server side of a task running in a process of its own."""

    def __init__(self, child: ChildProcess) -> None:
        self._child = child
        self._killed_for: str | None = None
        self._engines: dict[tuple, ResolvedEngine] = {}

    @classmethod
    def start(cls) -> TaskHost:
        return cls(ChildProcess.start("lazy_bird.task_host", error=TaskProcessError))

    @property
    def pid(self) -> int:
        return self._child.pid

    def memory_mb(self) -> float | None:
        return self._child.memory_mb()

    def kill(self, outcome: str) -> None:
        """End the task now; its run ends as if it had stopped for ``outcome`` ("pause", "cancel" or "interrupt")."""
        self._killed_for = outcome
        self._child.kill()

    def close(self) -> None:
        """After the run: the process ends by itself; make sure it did."""
        if not self._child.wait(5):
            self._child.kill()
        self._child.kill()

    def run(self, task: TaskOut, definition: TaskDefinition, context: TaskContext, scheduler: Scheduler) -> Any:
        """Run the task in the process and serve it until it ends; raises like the task would."""
        from lazy_bird import database, preferences
        from lazy_bird.crud.engine import EngineFamily

        connection = self._child.connection
        spec = {
            "task_id": task.id,
            "kind": task.kind,
            "module": definition.function.__module__,
            "params": task.params,
            "state": context.state,
            "database": database.connection_spec(),
            "preferences": str(preferences.PREFERENCE_FILE),
            "engines": [(family.package.rsplit(".", 1)[0], kind, family.module_names()) for kind, family in EngineFamily.families.items()],
        }
        try:
            connection.send(("run", spec))
            while True:
                message = connection.recv()
                kind = message[0]
                if kind == "progress":
                    _, progress, text, state = message
                    if state is not None:
                        context.state = dict(state)
                    scheduler.record_progress(task.id, progress, text, state)
                elif kind == "control":
                    connection.send(scheduler.control_of(task.id))
                elif kind == "engine":
                    connection.send(self._engine_call(*message[1:]))
                else:
                    context.state = dict(message[2] or {})
                    if kind == "done":
                        return message[1]
                    if kind == "stopped":
                        raise STOPS[message[1]]()
                    raise _remote_error(message[1])
        except (EOFError, OSError):
            if self._killed_for is not None:
                raise STOPS[self._killed_for]() from None
            self._child.wait(1)
            code = self._child.exit_code
            raise TaskProcessError(
                f"The task's process stopped unexpectedly (exit code {code}); it may have run out of memory.",
                code="task_crashed",
                details={"exit_code": code},
            ) from None

    def _engine_call(self, kind: str, engine_id: int, settings: dict, preset_id: int | None, operation: str, args: tuple) -> tuple[str, Any]:
        from lazy_bird.crud.engine import EngineFamily
        from lazy_bird.residency import ModelEvicted

        key = (kind, engine_id, preset_id, json.dumps(settings, sort_keys=True, default=str))
        try:
            resolved = self._engines.get(key)
            if resolved is None:
                resolved = self._engines[key] = EngineFamily.families[kind].resolve_settings(engine_id, settings, preset_id)
            return "ok", resolved.call(operation, *args)
        except ModelEvicted:
            self.kill("interrupt")
            raise
        except Exception as error:
            return "error", error_payload(error)


# ------------------------------------------------------------------ child side
class ServerLink:
    """In a task process: the server, as the task's context and its models see it."""

    def __init__(self, connection) -> None:
        self._connection = connection
        self._exchange = threading.Lock()  # the task may call engines from several threads

    def record_progress(self, task_id: int, progress: float | None, message: str | None, state: dict | None) -> None:
        with self._exchange:
            self._connection.send(("progress", progress, message, state))

    def control_of(self, task_id: int) -> str | None:
        with self._exchange:
            self._connection.send(("control",))
            return self._connection.recv()

    def engine(self, resolved: ResolvedEngine, operation: str, args: tuple) -> Any:
        with self._exchange:
            self._connection.send(("engine", resolved.kind, resolved.engine.id, resolved.settings.model_dump(), resolved.preset_id, operation, args))
            status, value = self._connection.recv()
        if status == "error":
            raise _remote_error(value)
        return value


class ServerResidency:
    """In a task process: the models are the server's, so calls on them are sent there."""

    def __init__(self, link: ServerLink) -> None:
        self._link = link

    @contextmanager
    def use(self, resolved: ResolvedEngine) -> Iterator[None]:
        yield None  # the server holds the task's models for its whole run

    def call(self, resolved: ResolvedEngine, operation: str, args: tuple) -> Any:
        return self._link.engine(resolved, operation, args)


def serve() -> None:
    """Child process entry point: set up like the server, run the task, report how it ended."""
    from lazy_bird import database, preferences
    from lazy_bird import residency as residency_module
    from lazy_bird.crud.engine import EngineFamily
    from lazy_bird.tasks.context import TaskContext
    from lazy_bird.tasks.registry import definition

    connection, _ = connect_to_parent()
    try:
        _, spec = connection.recv()
        context = None
        try:
            preferences.PREFERENCE_FILE = Path(spec["preferences"])
            database.attach(spec["database"])
            for package, kind, module_names in spec["engines"]:
                try:
                    importlib.import_module(package)
                except ImportError as error:
                    logger.warning("Engine family {} is not available in this task process: {}", kind, error)
                    continue
                EngineFamily.families[kind].load_modules(module_names)
            link = ServerLink(connection)
            residency_module._residency = ServerResidency(link)
            importlib.import_module(spec["module"])
            task_definition = definition(spec["kind"])
            if task_definition is None:
                raise LookupError(f"Module {spec['module']} does not declare the task kind '{spec['kind']}'.")
            context = TaskContext(spec["task_id"], spec["params"], spec["state"], link)
            outcome = ("done", task_definition.function(context, **spec["params"]))
        except TaskPaused:
            outcome = ("stopped", "paused")
        except TaskCancelled:
            outcome = ("stopped", "cancelled")
        except TaskInterrupted:
            outcome = ("stopped", "interrupted")
        except Exception as error:
            outcome = ("failed", error_payload(error))
        connection.send((*outcome, context.state if context is not None else spec["state"]))
    finally:
        connection.close()


if __name__ == "__main__":
    serve()
    # The run is over and reported. Threads it left behind (a download it stopped waiting for,
    # see TaskContext.run_blocking) must not keep the process alive: end it now, logs written.
    logger.remove()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
