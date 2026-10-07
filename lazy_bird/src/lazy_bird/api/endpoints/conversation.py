"""Conversations with agents: messages, runs and live streaming.

``/ws/conversations/{id}`` streams a run. Clients send
``{"type": "message", "content": "..."}`` (add a user message, then answer),
``{"type": "run"}`` (answer now, e.g. to retry after an error) or ``{"type": "stop"}``.
The server sends ``{"type": "conversation", "conversation"}`` on connection, then
during runs: ``message`` (every stored message), ``token`` / ``reasoning`` (deltas
of the answer being generated), ``tool_start``, ``status`` (generating,
retrying, waiting_resources, running_hooks, delegating), ``delegation`` (activity
of a sub-agent) and ``done`` (``reason``: completed, stopped or error). Problems
with a request are answered with ``{"type": "error", "error": {...}}``.
"""

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Response, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool

import lazy_bird.crud.conversation as ConversationCrud
from lazy_bird import inference
from lazy_bird.errors import AppError, InvalidInputError
from lazy_bird.inference.types import CallbackEmitter
from lazy_bird.schemas.conversation import (
    ConversationDetail,
    ConversationIn,
    ConversationOut,
    ConversationUpdate,
    RewindIn,
    RunOptions,
    RunOut,
)
from lazy_bird.schemas.message import MessageOut, UserMessageIn

router = APIRouter(tags=["conversations"])


@router.get("/conversations/", response_model=list[ConversationOut])
def list_conversations(agent_id: int | None = None):
    """Most recently active first; ``agent_id`` limits them to one agent."""
    return ConversationCrud.get_all(agent_id)


@router.post("/conversations/", response_model=ConversationDetail, status_code=201)
def create_conversation(payload: ConversationIn):
    return ConversationCrud.create(payload.agent_id, payload.title)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: int):
    return ConversationCrud.detail(conversation_id)


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
def rename_conversation(conversation_id: int, payload: ConversationUpdate):
    return ConversationCrud.rename(conversation_id, payload.title)


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: int):
    ConversationCrud.delete(conversation_id)
    return Response(status_code=204)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def list_messages(conversation_id: int):
    return ConversationCrud.detail(conversation_id).messages


@router.post("/conversations/{conversation_id}/messages", response_model=MessageOut, status_code=201)
def add_message(conversation_id: int, payload: UserMessageIn):
    """Add a user message (the agent answers on the next run)."""
    ConversationCrud.get(conversation_id)
    return ConversationCrud.add_user_message(conversation_id, payload.content)


@router.post("/conversations/{conversation_id}/run", response_model=RunOut)
def run_conversation(conversation_id: int, options: RunOptions | None = None):
    """Let the agent answer, without streaming; returns the messages it added."""
    options = options or RunOptions()
    outcome = inference.agentic_loop(conversation_id, retry=options.retry, max_iter=options.max_iter)
    return RunOut(reason=outcome.reason, messages=outcome.messages)


@router.post("/conversations/{conversation_id}/stop")
def stop_conversation(conversation_id: int) -> dict[str, bool]:
    """Ask a running answer to stop (the partial answer is kept)."""
    return {"stopped": inference.stop(conversation_id)}


@router.post("/conversations/{conversation_id}/rewind", response_model=ConversationDetail)
def rewind_conversation(conversation_id: int, payload: RewindIn):
    """Delete the messages after one, to regenerate an answer or resend an edited prompt."""
    return ConversationCrud.rewind(conversation_id, payload.message_id)


def _parse(text: str) -> dict[str, Any]:
    try:
        command = json.loads(text)
    except ValueError:
        command = None
    if not isinstance(command, dict):
        raise InvalidInputError("Commands must be JSON objects.", code="invalid_command")
    return command


@router.websocket("/ws/conversations/{conversation_id}")
async def conversation_socket(websocket: WebSocket, conversation_id: int):
    await websocket.accept()
    loop = asyncio.get_running_loop()
    outgoing: asyncio.Queue = asyncio.Queue()
    emitter = CallbackEmitter(lambda payload: loop.call_soon_threadsafe(outgoing.put_nowait, payload))
    running: asyncio.Future | None = None

    async def send_error(error: AppError) -> None:
        await websocket.send_json({"type": "error", "error": error.payload()["error"]})

    async def start(command: dict[str, Any]) -> asyncio.Future:
        nonlocal emitter
        if command.get("type") == "message":
            content = str(command.get("content", "")).strip()
            if not content:
                raise InvalidInputError("The message is empty.", code="empty_message")
            message = await run_in_threadpool(ConversationCrud.add_user_message, conversation_id, content)
            await websocket.send_json({"type": "message", "message": message.model_dump(mode="json")})
        emitter = CallbackEmitter(lambda payload: loop.call_soon_threadsafe(outgoing.put_nowait, payload))
        options = RunOptions.model_validate({key: command[key] for key in ("retry", "max_iter") if key in command})
        return asyncio.ensure_future(
            run_in_threadpool(inference.agentic_loop, conversation_id, emit=emitter, retry=options.retry, max_iter=options.max_iter)
        )

    try:
        detail = await run_in_threadpool(ConversationCrud.detail, conversation_id)
        await websocket.send_json({"type": "conversation", "conversation": detail.model_dump(mode="json")})
        receive = asyncio.ensure_future(websocket.receive_text())
        pending_event = asyncio.ensure_future(outgoing.get())
        while True:
            waiting = {receive, pending_event} | ({running} if running else set())
            done, _ = await asyncio.wait(waiting, return_when=asyncio.FIRST_COMPLETED)
            if pending_event in done:
                await websocket.send_json(pending_event.result())
                pending_event = asyncio.ensure_future(outgoing.get())
            if running is not None and running in done:
                error = running.exception()
                running = None
                if isinstance(error, AppError):
                    await send_error(error)
                elif error is not None:
                    await websocket.send_json({"type": "error", "error": {"code": "internal_error", "message": "The run failed unexpectedly.", "details": {}}})
            if receive in done:
                text = receive.result()
                receive = asyncio.ensure_future(websocket.receive_text())
                try:
                    command = _parse(text)
                    if command.get("type") == "stop":
                        emitter.stop()
                    elif command.get("type") in ("message", "run"):
                        if running is not None:
                            raise InvalidInputError("The agent is already answering; stop it first.", code="conversation_busy")
                        running = await start(command)
                    else:
                        raise InvalidInputError(f"Unknown command type '{command.get('type')}'.", code="invalid_command")
                except AppError as error:
                    await send_error(error)
    except WebSocketDisconnect:
        emitter.stop()
    except AppError as error:
        await send_error(error)
        await websocket.close()
    finally:
        for task in [locals().get("receive"), locals().get("pending_event")]:
            if task is not None:
                task.cancel()
