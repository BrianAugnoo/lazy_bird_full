"""Tasks over HTTP and WebSocket.

``/ws/tasks`` first sends ``{"type": "snapshot", "tasks", "resources", "kinds"}``,
then every change: ``{"type": "task", "task"}``, ``{"type": "task_deleted", "id"}``,
``{"type": "resources", "resources"}`` (capacity, used, holders and the models in memory),
``{"type": "task_unresponsive", "task_id"}``, ``{"type": "waiting", "waiting"}`` and
``{"type": "reordered"}`` (refetch the order). Clients send commands:

    {"action": "pause" | "resume" | "cancel" | "retry" | "delete", "task_id": 1, "request_id": "a"}
    {"action": "move", "task_id": 1, "before_id": 2}            # or "after_id"
    {"action": "update", "task_id": 1, "priority": 1}            # and/or "run_at"

and receive ``{"type": "ack", "request_id", "task"}`` or ``{"type": "error", "request_id", "error"}``.
"""

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Query, Response, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError

from lazy_bird.errors import AppError, InvalidInputError
from lazy_bird.schemas.task import TaskKindOut, TaskMove, TaskOut, TaskUpdate
from lazy_bird.tasks import definitions, scheduler

router = APIRouter(tags=["tasks"])


def _kinds() -> list[TaskKindOut]:
    return [
        TaskKindOut(kind=item.kind, title=item.title, description=item.description, priority=item.priority, retries=item.retries, isolated=item.isolated)
        for item in definitions()
    ]


@router.get("/tasks/", response_model=list[TaskOut])
def list_tasks(status: list[str] | None = Query(default=None), kind: str | None = None):
    return scheduler().tasks(status, kind)


@router.get("/tasks/kinds", response_model=list[TaskKindOut])
def list_task_kinds():
    return _kinds()


@router.get("/tasks/resources")
def get_resources() -> dict[str, Any]:
    return scheduler().resources()


@router.delete("/tasks/finished")
def clear_finished_tasks() -> dict[str, int]:
    return {"deleted": scheduler().clear_finished()}


@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: int):
    return scheduler().task(task_id)


@router.post("/tasks/{task_id}/pause", response_model=TaskOut)
def pause_task(task_id: int):
    return scheduler().pause(task_id)


@router.post("/tasks/{task_id}/resume", response_model=TaskOut)
def resume_task(task_id: int):
    return scheduler().resume(task_id)


@router.post("/tasks/{task_id}/cancel", response_model=TaskOut)
def cancel_task(task_id: int):
    return scheduler().cancel(task_id)


@router.post("/tasks/{task_id}/retry", response_model=TaskOut)
def retry_task(task_id: int):
    return scheduler().retry(task_id)


@router.post("/tasks/{task_id}/move", response_model=TaskOut)
def move_task(task_id: int, payload: TaskMove):
    return scheduler().move(task_id, payload.before_id, payload.after_id)


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, payload: TaskUpdate):
    return scheduler().update(task_id, payload.model_dump(exclude_unset=True))


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    scheduler().delete(task_id)
    return Response(status_code=204)


def _run_command(command: dict[str, Any]) -> dict[str, Any] | None:
    action, task_id = command.get("action"), command.get("task_id")
    if not isinstance(task_id, int):
        raise InvalidInputError("Commands need an integer task_id.", code="invalid_command")
    current = scheduler()
    simple = {"pause": current.pause, "resume": current.resume, "cancel": current.cancel, "retry": current.retry}
    if action in simple:
        return simple[action](task_id).model_dump(mode="json")
    if action == "delete":
        current.delete(task_id)
        return None
    if action == "move":
        move = TaskMove.model_validate(command)
        return current.move(task_id, move.before_id, move.after_id).model_dump(mode="json")
    if action == "update":
        changes = TaskUpdate.model_validate(command).model_dump(exclude_unset=True)
        return current.update(task_id, changes).model_dump(mode="json")
    raise InvalidInputError(f"Unknown action '{action}'.", code="invalid_command")


def _parse(text: str) -> Any:
    try:
        return json.loads(text)
    except ValueError:
        return None


async def _answer(websocket: WebSocket, command: Any) -> None:
    request_id = command.get("request_id") if isinstance(command, dict) else None
    try:
        if not isinstance(command, dict):
            raise InvalidInputError("Commands must be JSON objects.", code="invalid_command")
        task = await run_in_threadpool(_run_command, command)
        await websocket.send_json({"type": "ack", "request_id": request_id, "task": task})
    except AppError as error:
        await websocket.send_json({"type": "error", "request_id": request_id, "error": error.payload()["error"]})
    except ValidationError as error:
        await websocket.send_json({"type": "error", "request_id": request_id, "error": {"code": "invalid_command", "message": str(error), "details": {}}})


@router.websocket("/ws/tasks")
async def tasks_socket(websocket: WebSocket):
    await websocket.accept()
    current = scheduler()
    events = current.events.subscribe()
    try:
        tasks = await run_in_threadpool(current.tasks)
        await websocket.send_json(
            {
                "type": "snapshot",
                "tasks": [task.model_dump(mode="json") for task in tasks],
                "resources": current.resources(),
                "kinds": [kind.model_dump() for kind in _kinds()],
            }
        )
        receive = asyncio.ensure_future(websocket.receive_text())
        event = asyncio.ensure_future(events.get())
        while True:
            done, _ = await asyncio.wait({receive, event}, return_when=asyncio.FIRST_COMPLETED)
            if event in done:
                await websocket.send_json(event.result())
                event = asyncio.ensure_future(events.get())
            if receive in done:
                await _answer(websocket, _parse(receive.result()))
                receive = asyncio.ensure_future(websocket.receive_text())
    except WebSocketDisconnect:
        pass
    finally:
        current.events.unsubscribe(events)
        for pending in (locals().get("receive"), locals().get("event")):
            if pending is not None:
                pending.cancel()
