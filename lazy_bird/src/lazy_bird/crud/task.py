"""Persistence and state transitions of tasks.

Statuses: queued -> running -> completed | failed | cancelled, with paused as a
side state. A running task is only stopped at its checkpoints: pause and cancel
requests on running tasks are stored in ``control`` until then.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import case, delete as sql_delete, func, or_, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from lazy_bird.database import db
from lazy_bird.errors import ConflictError, NotFoundError
from lazy_bird.models.task import ACTIVE_STATUSES, TERMINAL_STATUSES, Task
from lazy_bird.schemas.task import TaskOut


class InvalidTaskTransitionError(ConflictError):
    code = "invalid_task_transition"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _row(session, task_id: int) -> Task:
    row = session.get(Task, task_id)
    if row is None:
        raise NotFoundError("Task", task_id)
    return row


def _save(session, row: Task) -> TaskOut:
    row.updated_at = _now()
    session.add(row)
    session.flush()
    result = TaskOut.model_validate(row)
    session.commit()
    return result


def _queue_end(session) -> int:
    return (session.exec(select(func.max(Task.position)).where(Task.status.in_(("queued", "paused")))).one() or 0) + 1


def _active_with_key(session, dedupe_key: str) -> Task | None:
    return session.exec(select(Task).where(Task.dedupe_key == dedupe_key, Task.status.in_(ACTIVE_STATUSES))).first()


def create(
    kind: str,
    title: str,
    params: dict[str, Any],
    *,
    priority: int,
    run_at: datetime | None,
    resources: dict[str, float],
    max_attempts: int,
    dedupe_key: str | None,
) -> tuple[TaskOut, bool]:
    """Insert a queued task; return ``(task, created)`` (False when deduplicated)."""
    with db() as session:
        if dedupe_key:
            existing = _active_with_key(session, dedupe_key)
            if existing is not None:
                return TaskOut.model_validate(existing), False
        row = Task(
            kind=kind,
            title=title,
            params=params,
            priority=priority,
            position=_queue_end(session),
            run_at=run_at,
            resources=resources,
            max_attempts=max_attempts,
            dedupe_key=dedupe_key,
        )
        session.add(row)
        try:
            session.flush()
            result = TaskOut.model_validate(row)
            session.commit()
        except IntegrityError:
            session.rollback()
            return TaskOut.model_validate(_active_with_key(session, dedupe_key)), False
        return result, True


def get(task_id: int) -> TaskOut:
    with db() as session:
        return TaskOut.model_validate(_row(session, task_id))


def list_tasks(statuses: list[str] | None = None, kind: str | None = None, limit: int = 200) -> list[TaskOut]:
    """Active tasks in queue order, then finished tasks, most recent first."""
    with db() as session:
        query = select(Task)
        if statuses:
            query = query.where(Task.status.in_(statuses))
        if kind:
            query = query.where(Task.kind == kind)
        active = session.exec(query.where(Task.status.in_(ACTIVE_STATUSES)).order_by(
            case((Task.status == "running", 0), else_=1), Task.priority, Task.position, Task.id
        ).limit(limit if limit >= 0 else None)).all()
        remaining = limit - len(active) if limit >= 0 else None
        finished = session.exec(query.where(Task.status.in_(TERMINAL_STATUSES)).order_by(
            func.coalesce(Task.finished_at, Task.updated_at).desc(), Task.id
        ).limit(remaining)).all() if remaining != 0 else []
        return [TaskOut.model_validate(row) for row in (active + finished)[:limit]]


def _queue_key(row: Task):
    return (0 if row.status == "running" else 1, row.priority, row.position, row.id)


def ready(now: datetime) -> list[Task]:
    """Queued tasks whose scheduled time has come, in execution order."""
    with db() as session:
        return list(session.exec(select(Task).where(
            Task.status == "queued", or_(Task.run_at.is_(None), Task.run_at <= _aware(now).astimezone(timezone.utc))
        ).order_by(Task.priority, Task.position, Task.id)).all())


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def claim(task_id: int) -> TaskOut | None:
    """Atomically move a queued task to running; None if another worker won."""
    with db() as session:
        claimed = session.execute(
            update(Task)
            .where(Task.id == task_id, Task.status == "queued")
            .values(status="running", control=None, started_at=_now(), updated_at=_now(), attempts=Task.attempts + 1)
        ).rowcount
        session.commit()
        return TaskOut.model_validate(_row(session, task_id)) if claimed else None


def record_progress(task_id: int, progress: float | None, message: str | None, state: dict | None) -> TaskOut:
    with db() as session:
        row = _row(session, task_id)
        if progress is not None:
            row.progress = max(0.0, min(1.0, float(progress)))
        if message is not None:
            row.message = message
        if state is not None:
            row.state = state
        return _save(session, row)


def state_of(task_id: int) -> dict:
    with db() as session:
        return dict(_row(session, task_id).state or {})


def finish(task_id: int, status: str, *, result: Any = None, error: dict | None = None, state: dict | None = None, refund_attempt: bool = False) -> TaskOut:
    """Record the end of a run: completed, failed, cancelled, paused or back to queued.

    ``refund_attempt``: the run was cut short from outside (shutdown, a more urgent
    request), so it does not count as one of the task's attempts.
    """
    with db() as session:
        row = _row(session, task_id)
        row.status = status
        row.control = None
        if state is not None:
            row.state = state
        if status in TERMINAL_STATUSES:
            row.finished_at = _now()
            row.result = result
            row.error = error
        if status == "queued":
            row.position = _queue_end(session)
            if refund_attempt:
                row.attempts = max(0, row.attempts - 1)
        return _save(session, row)


def retry_later(task_id: int, run_at: datetime, error: dict) -> TaskOut:
    with db() as session:
        row = _row(session, task_id)
        row.status, row.control, row.run_at, row.error = "queued", None, run_at, error
        return _save(session, row)


def set_control(task_id: int, control: str | None) -> TaskOut:
    with db() as session:
        row = _row(session, task_id)
        row.control = control
        return _save(session, row)


def requeue_interrupted() -> int:
    """Put back in the queue the tasks that were running when the server stopped."""
    with db() as session:
        count = session.execute(
            update(Task).where(Task.status == "running").values(status="queued", control=None, updated_at=_now())
        ).rowcount
        session.commit()
        return count


def _require(row: Task, allowed: tuple[str, ...], action: str) -> None:
    if row.status not in allowed:
        raise InvalidTaskTransitionError(
            f"Cannot {action} a {row.status} task.", details={"task_id": row.id, "status": row.status}
        )


def pause(task_id: int) -> TaskOut:
    """Pause a queued task now, or ask a running one to pause at its next checkpoint."""
    with db() as session:
        row = _row(session, task_id)
        _require(row, ("queued", "running"), "pause")
        if row.status == "queued":
            row.status = "paused"
        else:
            row.control = "pause"
        return _save(session, row)


def resume(task_id: int) -> TaskOut:
    with db() as session:
        row = _row(session, task_id)
        _require(row, ("paused",), "resume")
        row.status = "queued"
        return _save(session, row)


def cancel(task_id: int) -> TaskOut:
    with db() as session:
        row = _row(session, task_id)
        _require(row, ACTIVE_STATUSES, "cancel")
        if row.status == "running":
            row.control = "cancel"
        else:
            row.status, row.finished_at = "cancelled", _now()
        return _save(session, row)


def retry(task_id: int) -> TaskOut:
    """Run a failed or cancelled task again, from scratch."""
    with db() as session:
        row = _row(session, task_id)
        _require(row, ("failed", "cancelled"), "retry")
        if row.dedupe_key and _active_with_key(session, row.dedupe_key) is not None:
            raise InvalidTaskTransitionError("An equivalent task is already active.", details={"dedupe_key": row.dedupe_key})
        row.status, row.state, row.error, row.result = "queued", {}, None, None
        row.progress, row.message, row.finished_at, row.run_at = None, None, None, None
        row.position = _queue_end(session)
        return _save(session, row)


def update_task(task_id: int, changes: dict[str, Any]) -> TaskOut:
    with db() as session:
        row = _row(session, task_id)
        _require(row, ("queued", "paused"), "reschedule")
        for name in ("priority", "run_at"):
            if name in changes:
                setattr(row, name, changes[name])
        return _save(session, row)


def move(task_id: int, before_id: int | None = None, after_id: int | None = None) -> TaskOut:
    """Place a waiting task next to another one; it takes that task's priority."""
    if (before_id is None) == (after_id is None):
        raise InvalidTaskTransitionError("Give exactly one of before_id or after_id.")
    with db() as session:
        row = _row(session, task_id)
        anchor = _row(session, before_id if before_id is not None else after_id)
        _require(row, ("queued", "paused"), "move")
        _require(anchor, ("queued", "paused"), "move next to")
        siblings = sorted(
            session.exec(select(Task).where(Task.status.in_(("queued", "paused")), Task.priority == anchor.priority, Task.id != row.id)).all(),
            key=_queue_key,
        )
        index = next(i for i, sibling in enumerate(siblings) if sibling.id == anchor.id)
        siblings.insert(index if before_id is not None else index + 1, row)
        row.priority = anchor.priority
        for position, sibling in enumerate(siblings, start=1):
            sibling.position = position
            session.add(sibling)
        return _save(session, row)


def delete(task_id: int) -> None:
    with db() as session:
        row = _row(session, task_id)
        _require(row, TERMINAL_STATUSES, "delete")
        session.delete(row)
        session.commit()


def clear_finished() -> int:
    with db() as session:
        count = session.execute(sql_delete(Task).where(Task.status.in_(TERMINAL_STATUSES))).rowcount
        session.commit()
        return count


def prune_finished(keep: int) -> int:
    """Delete the oldest finished tasks beyond the ``keep`` most recent ones."""
    with db() as session:
        expired = select(Task.id).where(Task.status.in_(TERMINAL_STATUSES)).order_by(Task.finished_at.desc(), Task.id.desc()).offset(keep)
        count = session.execute(sql_delete(Task).where(Task.id.in_(expired)).execution_options(synchronize_session=False)).rowcount
        session.commit()
        return count
