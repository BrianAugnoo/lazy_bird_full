"""Processing states of files.

Every file has one row per ``(processor, target)``:

- ``chunking`` (target ``""``): the file split into chunks, needed by the others;
- ``embedding`` (target = model name): vectors of the chunks in that model's table.

States (``TRANSITIONS`` lists the allowed moves; any other one is a bug and raises):

- ``pending``: wanted; queued as soon as its dependency is up to date. ``error`` tells
  why it could not be queued yet (for instance no preset for that model);
- ``queued`` / ``running`` / ``paused``: mirror the task computing it (``task_id``);
- ``done``: computed from the current content (``content_hash`` = file hash);
- ``failed``: the last run failed (``error``); rerun on request or when the file changes;
- ``cancelled``: the user cancelled it; rerun on request or when the file changes;
- ``outdated``: computed from an older content, or its inputs were replaced;
- ``unsupported``: cannot be computed for this file (no chunker for its format).

Tasks never write these states: ``on_task_change`` maps the status changes of
processing tasks onto their rows (running, paused, completed -> done...).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from sqlmodel import select

from lazy_bird.database import db
from lazy_bird.errors import AppError, ConflictError, NotFoundError
from lazy_bird.models.file import File
from lazy_bird.models.file_processing import FileProcessing
from lazy_bird.schemas.files import ProcessingOut
from lazy_bird.crud import task as task_crud
from lazy_bird.schemas.task import TaskOut

TRANSITIONS: dict[str, set[str]] = {
    "pending": {"queued", "running", "paused", "unsupported"},
    "queued": {"running", "paused", "cancelled", "failed", "outdated", "unsupported"},
    "running": {"done", "failed", "paused", "cancelled", "queued", "outdated", "unsupported"},
    "paused": {"queued", "cancelled", "outdated"},
    "done": {"outdated", "pending"},
    "failed": {"queued", "outdated", "pending"},
    "cancelled": {"queued", "outdated", "pending"},
    "outdated": {"pending"},
    "unsupported": {"pending"},
}
ACTIVE_STATES = ("queued", "running", "paused")


class InvalidProcessingTransitionError(ConflictError):
    code = "invalid_processing_transition"


@dataclass(frozen=True)
class Processor:
    name: str
    task_kind: str
    requires: str | None
    params: Callable[[int, str], dict]
    title: Callable[[File, str], str]


def _embedding_params(file_id: int, target: str) -> dict:
    return {"file_id": file_id, "target": target, "preset_id": embedding_preset_for(target)}


PROCESSORS: dict[str, Processor] = {
    "chunking": Processor(
        "chunking", "files.chunk", None, lambda file_id, target: {"file_id": file_id}, lambda file, target: f"Chunk {file.name}{file.extension}"
    ),
    "embedding": Processor(
        "embedding", "files.embed", "chunking", _embedding_params, lambda file, target: f"Embed {file.name}{file.extension} ({target})"
    ),
}


def register_processor(processor: Processor) -> None:
    """Add a processing type (an extension such as LATTICE). Its task must take ``file_id``."""
    PROCESSORS[processor.name] = processor


def _processor_of_kind(kind: str) -> Processor | None:
    return next((processor for processor in PROCESSORS.values() if processor.task_kind == kind), None)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _move(row: FileProcessing, state: str) -> bool:
    """Apply a transition; return whether the state changed."""
    if row.state == state:
        return False
    if state not in TRANSITIONS[row.state]:
        raise InvalidProcessingTransitionError(
            f"A {row.processor} result cannot go from {row.state} to {state}.",
            details={"file_id": row.file_id, "processor": row.processor, "target": row.target, "from": row.state, "to": state},
        )
    row.state = state
    row.updated_at = _now()
    return True


def is_current(row: FileProcessing, file: File) -> bool:
    return row.state == "done" and row.content_hash is not None and row.content_hash == file.content_hash


def effective_state(row: FileProcessing, file: File) -> str:
    """The stored state, except a ``done`` result computed from another content."""
    return "outdated" if row.state == "done" and not is_current(row, file) else row.state


def summarize(file: File, rows: list[FileProcessing]) -> str:
    if file.missing:
        return "missing"
    if not rows:
        return "new"
    states = {effective_state(row, file) for row in rows}
    for group, summary in (
        (ACTIVE_STATES, "processing"),
        (("failed",), "error"),
        (("outdated",), "outdated"),
        (("pending", "cancelled"), "pending"),
        (("unsupported",), "unsupported"),
    ):
        if states & set(group):
            return summary
    return "ready"


def to_out(row: FileProcessing, file: File) -> ProcessingOut:
    return ProcessingOut.model_validate(row).model_copy(update={"state": effective_state(row, file)})


def rows_for(file_ids: list[int]) -> dict[int, list[FileProcessing]]:
    if not file_ids:
        return {}
    with db() as session:
        rows = session.exec(
            select(FileProcessing).where(FileProcessing.file_id.in_(file_ids)).order_by(FileProcessing.processor, FileProcessing.target)
        ).all()
    grouped: dict[int, list[FileProcessing]] = {file_id: [] for file_id in file_ids}
    for row in rows:
        grouped[row.file_id].append(row)
    return grouped


def _row(session, file_id: int, processor: str, target: str, create: bool = False) -> FileProcessing | None:
    row = session.exec(
        select(FileProcessing).where(FileProcessing.file_id == file_id, FileProcessing.processor == processor, FileProcessing.target == target)
    ).first()
    if row is None and create:
        row = FileProcessing(file_id=file_id, processor=processor, target=target)
        session.add(row)
        session.flush()
    return row


# --------------------------------------------------------------------------- wanted
def embedding_preset_for(target: str) -> int:
    """The preset embedding with ``target``: the default one when it matches, else the first valid one."""
    from lazy_bird.embedding import engine_family, vector_space

    presets = sorted(engine_family.presets(), key=lambda preset: (not preset.default, preset.id))
    for preset in presets:
        if not preset.valid:
            continue
        try:
            if vector_space(engine_family.resolve(preset.id)) == target:
                return preset.id
        except AppError:
            continue
    raise NotFoundError("Embedding preset for model", target, code="no_preset_for_model")


def automatic_targets() -> list[tuple[str, str]]:
    """What every file should get: its chunks, and vectors from the default embedding preset."""
    from lazy_bird.embedding import engine_family, vector_space

    wanted = [("chunking", "")]
    try:
        wanted.append(("embedding", vector_space(engine_family.resolve())))
    except AppError:
        pass
    return wanted


def ensure(file_id: int, *, automatic: bool = True, wanted: list[tuple[str, str]] | None = None) -> list[TaskOut]:
    """Create the wanted rows, then queue every pending row whose dependency is up to date.

    ``automatic`` adds ``automatic_targets()`` to ``wanted``. Returns the queued tasks.
    """
    requested = list(wanted or []) + (automatic_targets() if automatic else [])
    with db() as session:
        file = session.get(File, file_id)
        if file is None:
            raise NotFoundError("File", file_id)
        if file.missing:
            return []
        for processor, target in requested:
            if processor not in PROCESSORS:
                raise NotFoundError("Processor", processor)
            row = _row(session, file_id, processor, target, create=True)
            if effective_state(row, file) == "outdated":
                row.state = "outdated"  # a done result whose hash no longer matches
                _move(row, "pending")
                session.add(row)
        session.commit()
        rows = {(row.processor, row.target): row for row in session.exec(select(FileProcessing).where(FileProcessing.file_id == file_id)).all()}
        ready = []
        for row in rows.values():
            if row.state != "pending":
                continue
            requires = PROCESSORS[row.processor].requires
            if requires is not None:
                upstream = rows.get((requires, ""))
                if upstream is not None and upstream.state == "unsupported":
                    _move(row, "unsupported")
                    row.error = {"code": "requirement_unsupported", "message": f"{requires} is not supported for this file."}
                    session.add(row)
                    continue
                if upstream is None or not is_current(upstream, file):
                    continue
            ready.append((row.processor, row.target))
        session.commit()
        snapshot = File.model_validate(file)
    return [task for task in (_queue(snapshot, processor, target) for processor, target in ready) if task is not None]


def _queue(file: File, processor_name: str, target: str) -> TaskOut | None:
    from lazy_bird import tasks

    processor = PROCESSORS[processor_name]
    definition = tasks.definition(processor.task_kind)
    if definition is None:
        tasks.discover_tasks()
        definition = tasks.definition(processor.task_kind)
    try:
        if definition is None:
            raise NotFoundError("Task kind", processor.task_kind)
        task = definition.submit(
            title=processor.title(file, target),
            dedupe_key=f"{processor_name}:{file.id}:{target}",
            **processor.params(file.id, target),
        )
    except AppError as error:
        _block(file.id, processor_name, target, {"code": error.code, "message": error.message})
        return None
    current = task_crud.get(task.id)
    if current.control != "cancel":
        on_task_change(current)  # links the row when an equivalent task was already active
    return current


def _block(file_id: int, processor: str, target: str, error: dict) -> None:
    """Keep a row pending with the reason it could not be queued (retried by the next ensure)."""
    with db() as session:
        row = _row(session, file_id, processor, target, create=True)
        row.error, row.updated_at = error, _now()
        session.add(row)
        session.commit()
    _publish_file(file_id)


def ensure_all(*, automatic: bool = True) -> int:
    """``ensure`` every file; return how many tasks were queued."""
    with db() as session:
        file_ids = list(session.exec(select(File.id).where(File.missing == False)).all())  # noqa: E712
    return sum(len(ensure(file_id, automatic=automatic)) for file_id in file_ids)


def request(file_id: int, processor: str, target: str = "") -> list[TaskOut]:
    """Compute one processing again, even if it is up to date."""
    with db() as session:
        if session.get(File, file_id) is None:
            raise NotFoundError("File", file_id)
        row = _row(session, file_id, processor, target)
        if row is not None and row.state not in (*ACTIVE_STATES, "pending"):
            _move(row, "pending")
            session.add(row)
            session.commit()
    return ensure(file_id, automatic=False, wanted=[(processor, target)])


# ------------------------------------------------------------------- invalidations
def _outdate(session, rows: list[FileProcessing], reason: str) -> list[int]:
    """Mark results outdated; return the tasks still computing them, to cancel."""
    to_cancel = []
    for row in rows:
        if row.state in ACTIVE_STATES and row.task_id is not None:
            to_cancel.append(row.task_id)
        if row.state in ("done", "failed", "cancelled", *ACTIVE_STATES):
            _move(row, "outdated")
            row.error = {"code": "outdated", "message": reason}
            session.add(row)
    return to_cancel


def _cancel_tasks(task_ids: list[int]) -> None:
    from lazy_bird.tasks import scheduler

    for task_id in task_ids:
        try:
            scheduler().cancel(task_id)
        except AppError:
            pass


def on_content_changed(file_id: int) -> None:
    """The file content changed: every result computed from the old content is outdated.

    Results still being computed are cancelled; the end of their runs reschedules them.
    """
    from lazy_bird.preferences import auto_embedding_enabled

    with db() as session:
        rows = session.exec(select(FileProcessing).where(FileProcessing.file_id == file_id)).all()
        to_cancel = _outdate(session, list(rows), "The file content changed.")
        session.commit()
    _cancel_tasks(to_cancel)
    if not to_cancel:
        ensure(file_id, automatic=auto_embedding_enabled())
    _publish_file(file_id)


def on_chunks_replaced(file_id: int) -> None:
    """New chunks: vectors of the old ones were deleted, so every embedding is outdated."""
    with db() as session:
        rows = session.exec(select(FileProcessing).where(FileProcessing.file_id == file_id, FileProcessing.processor == "embedding")).all()
        to_cancel = _outdate(session, list(rows), "The chunks of the file were recomputed.")
        session.commit()
    _cancel_tasks(to_cancel)


def outdate_processor(processor: str, reason: str, target: str | None = None) -> None:
    """Outdate one processing for every file (e.g. embeddings after a vector database switch)."""
    with db() as session:
        query = select(FileProcessing).where(FileProcessing.processor == processor)
        if target is not None:
            query = query.where(FileProcessing.target == target)
        to_cancel = _outdate(session, list(session.exec(query).all()), reason)
        session.commit()
    _cancel_tasks(to_cancel)


def forget_target(processor: str, target: str) -> int:
    """Delete the rows of a result that no longer exists anywhere (a dropped vector table)."""
    with db() as session:
        rows = session.exec(select(FileProcessing).where(FileProcessing.processor == processor, FileProcessing.target == target)).all()
        for row in rows:
            session.delete(row)
        session.commit()
        return len(rows)


# ----------------------------------------------------------------- task listener
def on_task_change(task: TaskOut) -> None:
    """Mirror a processing task's status onto its row (registered with the scheduler)."""
    processor = _processor_of_kind(task.kind)
    file_id = task.params.get("file_id")
    if processor is None or not isinstance(file_id, int):
        return
    target = str(task.params.get("target", ""))
    with db() as session:
        file = session.get(File, file_id)
        if file is None:
            return
        row = _row(session, file_id, processor.name, target, create=True)
        changed = _apply(row, task, file)
        session.add(row)
        session.commit()
        state = row.state
    if changed and task.status == "completed" and processor.name == "chunking":
        on_chunks_replaced(file_id)
    if changed and (task.status == "completed" or state in ("outdated", "unsupported")):
        from lazy_bird.preferences import auto_embedding_enabled

        ensure(file_id, automatic=auto_embedding_enabled())
    if changed:
        _publish_file(file_id)


def _apply(row: FileProcessing, task: TaskOut, file: File) -> bool:
    """Move a row according to its task's status; return whether anything changed."""
    if task.status in ("queued", "running", "paused"):
        if row.task_id == task.id and row.state == "outdated":
            return False  # invalidated while active: its cancellation is on the way
        if task.status == "queued":
            row.task_id, row.error = task.id, None
            return _move(row, "queued")
        if task.status == "running" and row.state != "running":
            row.task_id, row.content_hash, row.error = task.id, file.content_hash, None
        row.task_id = task.id
        return _move(row, task.status)
    if row.task_id is not None and row.task_id != task.id:
        return False  # end of an older run that no longer owns this row
    if row.state not in ACTIVE_STATES:
        row.task_id = None
        return True  # the run ended after the row was invalidated: ensure() reschedules it
    row.task_id = None
    if task.status == "completed":
        return _move(row, "done" if row.content_hash == file.content_hash else "outdated")
    if task.status == "failed":
        row.error = task.error
        return _move(row, "unsupported" if (task.error or {}).get("code") == "unsupported_format" else "failed")
    if task.status == "cancelled":
        return _move(row, "cancelled")
    return False


def _publish_file(file_id: int) -> None:
    from lazy_bird.tasks import publish

    publish({"type": "file", "file_id": file_id})
