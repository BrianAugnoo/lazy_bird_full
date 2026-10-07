"""The scheduler: picks queued tasks and runs them in worker threads.

Scheduling pass (on every wake-up, at least once per ``poll_interval``):

1. queued tasks whose ``run_at`` has come are taken in order: priority (high first),
   then position (manual order), then age;
2. a task starts when a worker is free and its resources fit in the pool;
3. a task that does not fit blocks every later task needing one of the missing
   resources (so a large GPU job is not starved by smaller ones), while tasks that
   need other resources can still start.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from loguru import logger

from lazy_bird.crud import task as task_crud
from lazy_bird.errors import AppError
from lazy_bird.schemas.task import TaskOut
from lazy_bird.tasks.context import TaskContext
from lazy_bird.tasks.events import EventHub
from lazy_bird.tasks.registry import TaskCancelled, TaskDefinition, TaskInterrupted, TaskPaused, definition, listeners
from lazy_bird.tasks.resources import InsufficientResourcesError, ResourcePool

RETRY_DELAY = timedelta(seconds=30)
FINISHED_TASKS_KEPT = 500


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _jsonable(value: Any) -> Any:
    try:
        from pydantic_core import to_jsonable_python

        return to_jsonable_python(value)
    except Exception:
        return repr(value)


def _error(error: BaseException) -> dict[str, Any]:
    if isinstance(error, AppError):
        return {"code": error.code, "message": error.message, "details": error.details}
    return {"code": type(error).__name__, "message": str(error) or type(error).__name__}


class Scheduler:
    def __init__(
        self,
        pool: ResourcePool,
        *,
        workers: int = 4,
        poll_interval: float = 1.0,
        now: Callable[[], datetime] = _utcnow,
    ) -> None:
        self.pool = pool
        self.workers = max(1, workers)
        self.poll_interval = poll_interval
        self.now = now
        self.events = EventHub()
        self._lock = threading.RLock()
        # Held while submitting and while claiming: a task's "queued" event always reaches
        # listeners before the task can start, so status events are seen in order.
        self._dispatch = threading.RLock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._executor: ThreadPoolExecutor | None = None
        self._running: set[int] = set()
        self._controls: dict[int, str] = {}
        self._waiting: dict[int, list[str]] = {}

    # ------------------------------------------------------------------ lifecycle
    @property
    def started(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.started:
            return
        requeued = task_crud.requeue_interrupted()
        if requeued:
            logger.info("Requeued {} task(s) interrupted by the last shutdown", requeued)
        self._stop.clear()
        self._executor = ThreadPoolExecutor(max_workers=self.workers, thread_name_prefix="lazy-bird-task")
        self._thread = threading.Thread(target=self._loop, name="lazy-bird-scheduler", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        """Stop scheduling; running tasks go back to the queue at their next checkpoint."""
        self._stop.set()
        self._wake.set()
        with self._lock:
            for task_id in self._running:
                self._controls[task_id] = "interrupt"
        if self._thread is not None:
            self._thread.join(timeout)
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            deadline = time.monotonic() + timeout
            while self._running and time.monotonic() < deadline:
                time.sleep(0.05)
        self._thread = None
        self._executor = None

    def wake(self) -> None:
        self._wake.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.schedule_once()
            except Exception:
                logger.exception("Task scheduling pass failed")
            self._wake.wait(self.poll_interval)
            self._wake.clear()

    # ----------------------------------------------------------------- scheduling
    def schedule_once(self) -> list[int]:
        """Start every task that can start now; return their ids."""
        with self._dispatch:
            return self._schedule()

    def _schedule(self) -> list[int]:
        started, waiting, blocked = [], {}, set()
        for row in task_crud.ready(self.now()):
            needs = {name: amount for name, amount in (row.resources or {}).items() if amount > 0}
            task_definition = definition(row.kind)
            if task_definition is None:
                self._publish(task_crud.finish(row.id, "failed", error={"code": "unknown_task_kind", "message": f"No task kind '{row.kind}' is installed."}))
                continue
            with self._lock:
                if len(self._running) >= self.workers:
                    waiting[row.id] = ["worker"]
                    continue
            if blocked & needs.keys():
                waiting[row.id] = sorted(blocked & needs.keys())
                continue
            try:
                self.pool.check(needs)
            except InsufficientResourcesError as error:
                self._publish(task_crud.finish(row.id, "failed", error=_error(error)))
                continue
            holder = f"task:{row.id}"
            if not self.pool.try_acquire(holder, needs):
                missing = self.pool.blocked_by(needs)
                blocked |= missing
                waiting[row.id] = sorted(missing)
                continue
            claimed = task_crud.claim(row.id)
            if claimed is None:
                self.pool.release(holder)
                continue
            self._launch(claimed, task_definition)
            started.append(row.id)
        self._update_waiting(waiting)
        return started

    def _update_waiting(self, waiting: dict[int, list[str]]) -> None:
        with self._lock:
            changed = waiting != self._waiting
            self._waiting = waiting
        if changed:
            self.events.publish({"type": "waiting", "waiting": {str(task_id): reasons for task_id, reasons in waiting.items()}})

    def _launch(self, task: TaskOut, task_definition: TaskDefinition) -> None:
        with self._lock:
            self._running.add(task.id)
        self._publish(task)
        self._publish_resources()
        context = TaskContext(task.id, task.params, task_crud.state_of(task.id), self)
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=self.workers, thread_name_prefix="lazy-bird-task")
        self._executor.submit(self._execute, task, task_definition, context)

    def _run(self, task: TaskOut, task_definition: TaskDefinition, context: TaskContext) -> TaskOut:
        """Call the task function and record how its run ended."""
        try:
            result = task_definition.function(context, **task.params)
            return task_crud.finish(task.id, "completed", result=_jsonable(result), state=context.state)
        except TaskPaused:
            return task_crud.finish(task.id, "paused", state=context.state)
        except TaskCancelled:
            return task_crud.finish(task.id, "cancelled", state=context.state)
        except TaskInterrupted:
            return task_crud.finish(task.id, "queued", state=context.state)
        except Exception as error:
            logger.opt(exception=error).error("Task {} ({}) failed", task.id, task.kind)
            if task.attempts < task.max_attempts:
                return task_crud.retry_later(task.id, self.now() + RETRY_DELAY, _error(error))
            return task_crud.finish(task.id, "failed", error=_error(error), state=context.state)

    def _execute(self, task: TaskOut, task_definition: TaskDefinition, context: TaskContext) -> None:
        try:
            outcome = self._run(task, task_definition, context)
            self._publish(outcome)
            if outcome.status in ("completed", "failed", "cancelled"):
                task_crud.prune_finished(FINISHED_TASKS_KEPT)
        except Exception:
            logger.exception("Could not record the end of task {}", task.id)
        finally:
            self.pool.release(f"task:{task.id}")
            with self._lock:
                self._running.discard(task.id)
                self._controls.pop(task.id, None)
            self._publish_resources()
            self.wake()

    # -------------------------------------------------------------- task context
    def record_progress(self, task_id: int, progress: float | None, message: str | None, state: dict | None) -> None:
        self._publish(task_crud.record_progress(task_id, progress, message, state), status_changed=False)

    def control_of(self, task_id: int) -> str | None:
        with self._lock:
            return self._controls.get(task_id)

    # -------------------------------------------------------------------- events
    def describe(self, task: TaskOut) -> TaskOut:
        with self._lock:
            reasons = list(self._waiting.get(task.id, []))
        if task.status == "queued" and task.run_at is not None:
            run_at = task.run_at if task.run_at.tzinfo else task.run_at.replace(tzinfo=timezone.utc)
            if run_at > self.now():
                reasons.append("schedule")
        return task.model_copy(update={"waiting_for": reasons})

    def _publish(self, task: TaskOut, status_changed: bool = True) -> TaskOut:
        described = self.describe(task)
        self.events.publish({"type": "task", "task": described.model_dump(mode="json")})
        if status_changed:
            for listener in listeners():
                try:
                    listener(described)
                except Exception:
                    logger.exception("Task listener {} failed for task {}", getattr(listener, "__name__", listener), task.id)
        return described

    def _publish_resources(self) -> None:
        self.events.publish({"type": "resources", "resources": self.pool.snapshot()})

    # ------------------------------------------------------------------- commands
    def submit(self, task_definition: TaskDefinition, params: dict[str, Any], *, title=None, priority=None, run_at=None, dedupe_key=None, resources=None) -> TaskOut:
        task_definition.check_params(params)
        needs = resources if resources is not None else task_definition.resources_for(params)
        self.pool.check({name: amount for name, amount in needs.items() if amount > 0})
        with self._dispatch:
            return self._create(task_definition, params, title, priority, run_at, dedupe_key, needs)

    def _create(self, task_definition, params, title, priority, run_at, dedupe_key, needs) -> TaskOut:
        task, created = task_crud.create(
            task_definition.kind,
            title or task_definition.title_for(params),
            params,
            priority=task_definition.priority if priority is None else priority,
            run_at=run_at,
            resources=needs,
            max_attempts=1 + task_definition.retries,
            dedupe_key=dedupe_key,
        )
        if created:
            self._publish(task)
            self.wake()
        return self.describe(task)

    def _command(self, change: Callable[[], TaskOut]) -> TaskOut:
        task = self._publish(change())
        self.wake()
        return task

    def pause(self, task_id: int) -> TaskOut:
        task = task_crud.pause(task_id)
        if task.status == "running":
            with self._lock:
                self._controls[task_id] = "pause"
        return self._command(lambda: task)

    def resume(self, task_id: int) -> TaskOut:
        return self._command(lambda: task_crud.resume(task_id))

    def cancel(self, task_id: int) -> TaskOut:
        task = task_crud.cancel(task_id)
        if task.status == "running":
            with self._lock:
                self._controls[task_id] = "cancel"
        return self._command(lambda: task)

    def retry(self, task_id: int) -> TaskOut:
        return self._command(lambda: task_crud.retry(task_id))

    def update(self, task_id: int, changes: dict[str, Any]) -> TaskOut:
        task = self._publish(task_crud.update_task(task_id, changes), status_changed=False)
        self.wake()
        return task

    def move(self, task_id: int, before_id: int | None = None, after_id: int | None = None) -> TaskOut:
        moved = self._publish(task_crud.move(task_id, before_id, after_id), status_changed=False)
        self.wake()
        self.events.publish({"type": "reordered"})
        return moved

    def delete(self, task_id: int) -> None:
        task_crud.delete(task_id)
        self.events.publish({"type": "task_deleted", "id": task_id})

    def clear_finished(self) -> int:
        count = task_crud.clear_finished()
        self.events.publish({"type": "reordered"})
        return count

    def tasks(self, statuses: list[str] | None = None, kind: str | None = None) -> list[TaskOut]:
        return [self.describe(task) for task in task_crud.list_tasks(statuses, kind)]

    def task(self, task_id: int) -> TaskOut:
        return self.describe(task_crud.get(task_id))
