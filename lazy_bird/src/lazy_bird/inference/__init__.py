"""Inference: run agents with the LLM configured in their ``meta``.

Engine contract (``inference/engines/<name>.py``, see ``crud/engine.py`` for the
shared part): ``chat(messages, tools, settings, model, emit) -> ChatResult``.
``messages`` are ``ChatMessage`` objects, ``tools`` OpenAI-style function
definitions, ``emit`` an ``Emitter`` receiving tokens while they are generated
(``emit.stopped`` asks the engine to stop). Engines raise ``EngineError`` with
``retryable`` set. An engine may define ``resources(settings, model)`` (e.g. VRAM
of a local model), held in the shared resource pool during each call.

Agent configuration: ``Agent.meta`` holds either ``preset_inference_engine_id`` or
``inference_engine_id`` + ``inference_settings`` (validated by ``agent_meta``).

Turn rules: an agent answers only when its conversation is runnable (last message
from the user, an error or an unfinished tool turn). Each step of the loop runs the
agent's hooks, reads the conversation, calls the engine (retrying failures up to
``retry`` times), then either runs the requested tools and continues, or stores the
answer. Failures end the run with an ``error`` message (``meta.code``).
"""

from __future__ import annotations

import json
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator, Literal

from loguru import logger
from pydantic import BaseModel, ValidationError, model_validator

from lazy_bird.crud.engine import EngineFamily, ResolvedEngine
from lazy_bird.errors import AppError, ConflictError, InvalidInputError, InvalidSettingsError, NotFoundError
from lazy_bird.extension.settings import validation_messages
from lazy_bird.inference.types import CallbackEmitter, ChatMessage, ChatResult, Emitter, EngineError, ToolCall
from lazy_bird.models.inference_engine import InferenceEngine, PresetInference
from lazy_bird.schemas.inference_engine import PresetInferenceOut
from lazy_bird.schemas.message import MessageOut

engine_family = EngineFamily(
    kind="inference",
    package="lazy_bird.inference.engines",
    required=("chat",),
    engine_table=InferenceEngine,
    preset_table=PresetInference,
    engine_fk="inference_engine_id",
    preset_out=PresetInferenceOut,
)

INFERENCE_KEYS = ("preset_inference_engine_id", "inference_engine_id", "inference_settings")
RESOURCE_TIMEOUT_SECONDS = 600
MAX_RETRY_DELAY_SECONDS = 8


def initialize_inference_engines():
    return engine_family.discover()


# ------------------------------------------------------------- agent configuration
class AgentInference(BaseModel):
    preset_inference_engine_id: int | None = None
    inference_engine_id: int | None = None
    inference_settings: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _one_source(self) -> "AgentInference":
        if (self.preset_inference_engine_id is None) == (self.inference_engine_id is None):
            raise ValueError("set either preset_inference_engine_id, or inference_engine_id with inference_settings")
        if self.preset_inference_engine_id is not None and self.inference_settings is not None:
            raise ValueError("inference_settings only goes with inference_engine_id")
        return self


def _meta_error(fields: dict[str, str]) -> InvalidInputError:
    return InvalidInputError("The agent's inference configuration is invalid.", code="invalid_agent_inference", details={"fields": fields})


def agent_meta(meta: dict[str, Any] | None) -> dict[str, Any]:
    """Validate the inference part of an agent's meta, defaulting to the default preset."""
    meta = dict(meta or {})
    if not any(key in meta for key in INFERENCE_KEYS):
        default = engine_family.default_preset()
        if default is None:
            raise InvalidInputError(
                "Create an inference preset first: every agent needs an LLM to answer with.",
                code="no_inference_preset",
                details={"fields": {"meta": "No inference preset exists"}},
            )
        meta["preset_inference_engine_id"] = default.id
    try:
        config = AgentInference.model_validate({key: meta.get(key) for key in INFERENCE_KEYS})
    except ValidationError as error:
        raise _meta_error({f"meta.{key}": message for key, message in validation_messages(error).items()}) from error
    try:
        if config.preset_inference_engine_id is not None:
            engine_family.preset(config.preset_inference_engine_id)
        else:
            meta["inference_settings"] = engine_family.check_kwargs(engine_family.engine(config.inference_engine_id), config.inference_settings)
    except InvalidSettingsError as error:
        raise _meta_error({f"meta.inference_settings.{key}": message for key, message in error.fields.items()}) from error
    except NotFoundError as error:
        raise _meta_error({"meta": error.message}) from error
    return meta


def resolve_for_agent(meta: dict[str, Any] | None) -> ResolvedEngine:
    """The engine an agent answers with."""
    try:
        config = AgentInference.model_validate({key: (meta or {}).get(key) for key in INFERENCE_KEYS})
    except ValidationError as error:
        raise InvalidInputError(
            "This agent has no inference configuration: choose an inference preset for it.",
            code="agent_without_inference",
            details={"fields": validation_messages(error)},
        ) from error
    if config.preset_inference_engine_id is not None:
        return engine_family.resolve(config.preset_inference_engine_id)
    return engine_family.resolve_settings(config.inference_engine_id, config.inference_settings)


# ---------------------------------------------------------------------- run state
class _Run(Emitter):
    """Wraps the caller's emitter with a stop flag usable from ``stop()``."""

    def __init__(self, inner: Emitter) -> None:
        self.inner = inner
        self._stop = threading.Event()

    def token(self, text: str) -> None:
        self.inner.token(text)

    def reasoning(self, text: str) -> None:
        self.inner.reasoning(text)

    def event(self, payload: dict[str, Any]) -> None:
        self.inner.event(payload)

    def stop(self) -> None:
        self._stop.set()

    @property
    def stopped(self) -> bool:
        return self._stop.is_set() or self.inner.stopped


_runs: dict[int, _Run] = {}
_runs_lock = threading.Lock()


def is_running(conversation_id: int) -> bool:
    with _runs_lock:
        return conversation_id in _runs


def stop(conversation_id: int) -> bool:
    """Ask a running conversation to stop; return whether one was running."""
    with _runs_lock:
        run = _runs.get(conversation_id)
    if run is not None:
        run.stop()
    return run is not None


@contextmanager
def _claim(conversation_id: int, emit: Emitter) -> Iterator[_Run]:
    run = _Run(emit)
    with _runs_lock:
        if conversation_id in _runs:
            raise ConflictError("The agent is already answering in this conversation.", code="conversation_busy")
        _runs[conversation_id] = run
    try:
        yield run
    finally:
        with _runs_lock:
            _runs.pop(conversation_id, None)


# ------------------------------------------------------------------- conversions
def to_chat_messages(messages: list[MessageOut]) -> list[ChatMessage]:
    """Stored messages as engines see them (errors are for users only)."""
    converted = []
    for message in messages:
        meta = message.meta or {}
        if message.role in ("system", "user", "assistant"):
            converted.append(ChatMessage(message.role, message.content or ""))
        elif message.role == "tool-calling":
            calls = tuple(ToolCall(call.get("id", ""), call.get("name", ""), call.get("arguments") or {}) for call in meta.get("tool_calls", []))
            converted.append(ChatMessage("assistant", message.content, tool_calls=calls))
        elif message.role == "tool-response":
            converted.append(ChatMessage("tool", message.content or "", tool_call_id=meta.get("tool_call_id"), name=meta.get("name")))
    return converted


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)


# ---------------------------------------------------------------------- the loop
@dataclass
class RunOutcome:
    reason: Literal["completed", "stopped", "error"]
    messages: list[MessageOut] = field(default_factory=list)

    @property
    def answer(self) -> MessageOut | None:
        return next((message for message in reversed(self.messages) if message.role in ("assistant", "error")), None)


class _Turn:
    """One run of the agentic loop over a conversation."""

    def __init__(self, conversation_id: int, run: _Run) -> None:
        self.conversation_id = conversation_id
        self.run = run
        self.created: list[MessageOut] = []

    def store(self, role: str, content: str | None, meta: dict[str, Any] | None = None) -> MessageOut:
        from lazy_bird.crud import message as message_crud

        message = message_crud.create(self.conversation_id, role, content, meta)
        self.created.append(message)
        self.run.event({"type": "message", "message": message.model_dump(mode="json")})
        return message

    def status(self, state: str, **details: Any) -> None:
        self.run.event({"type": "status", "state": state, **details})

    def finish(self, reason: str) -> RunOutcome:
        self.run.event({"type": "done", "reason": reason})
        return RunOutcome(reason, self.created)

    def fail(self, code: str, message: str, details: dict[str, Any] | None = None) -> RunOutcome:
        self.store("error", message, {"code": code, "details": details or {}})
        return self.finish("error")


@contextmanager
def _hold(resolved: ResolvedEngine, holder: str, turn: _Turn) -> Iterator[None]:
    estimate = getattr(resolved.module, "resources", None)
    needs = {name: amount for name, amount in (estimate(resolved.settings, resolved.model) if estimate else {}).items() if amount > 0}
    if not needs:
        yield
        return
    from lazy_bird.tasks import scheduler

    pool = scheduler().pool
    if not pool.fits(needs):
        turn.status("waiting_resources", needs=needs)
    if not pool.acquire(holder, needs, timeout=RESOURCE_TIMEOUT_SECONDS):
        raise EngineError("The resources this model needs stayed busy for too long.", code="resources_busy")
    try:
        yield
    finally:
        pool.release(holder)


def _call_engine(turn: _Turn, resolved: ResolvedEngine, messages: list[ChatMessage], tools: list[dict], retry: int) -> ChatResult | RunOutcome:
    for attempt in range(retry + 1):
        try:
            turn.status("generating", attempt=attempt + 1)
            with _hold(resolved, f"inference:{turn.conversation_id}", turn):
                return resolved.module.chat(messages, tools, resolved.settings, resolved.model, turn.run)
        except EngineError as error:
            if not error.retryable or attempt == retry:
                return turn.fail(error.code, error.message, {**error.details, "attempts": attempt + 1})
            reason = error.message
        except AppError as error:
            return turn.fail(error.code, error.message, error.details)
        except Exception as error:
            logger.opt(exception=error).error("Inference engine '{}' failed", resolved.engine.name)
            if attempt == retry:
                return turn.fail("engine_failed", f"The inference engine failed: {error}", {"attempts": attempt + 1})
            reason = str(error)
        delay = min(2**attempt, MAX_RETRY_DELAY_SECONDS)
        turn.status("retrying", attempt=attempt + 1, retry=retry, reason=reason, delay=delay)
        deadline = time.monotonic() + delay
        while time.monotonic() < deadline and not turn.run.stopped:
            time.sleep(0.1)
        if turn.run.stopped:
            return turn.finish("stopped")
    raise AssertionError("unreachable")


def _run_tools(turn: _Turn, runtime, calls: list[dict[str, Any]]) -> None:
    for call in calls:
        if turn.run.stopped:
            return
        name, arguments = call.get("name", ""), call.get("arguments") or {}
        turn.run.event({"type": "tool_start", "call": call})
        status = "ok"
        if "__invalid_json__" in arguments:
            content, status = "Error: the tool arguments were not valid JSON.", "error"
        else:
            try:
                content = _text(runtime.call_tool(name, arguments))
            except AppError as error:
                content, status = f"Error: {error.message}", "error"
            except Exception as error:
                logger.opt(exception=error).warning("Tool '{}' failed", name)
                content, status = f"Error while running {name}: {error}", "error"
        turn.store("tool-response", content, {"tool_call_id": call.get("id"), "name": name, "status": status})


def agentic_loop(conversation_id: int, *, emit: Emitter | None = None, retry: int = 3, max_iter: int = 20) -> RunOutcome:
    """Let the conversation's agent answer, using tools as needed; see the module docstring."""
    from lazy_bird.agents.runtime import build
    from lazy_bird.crud import agent as agent_crud
    from lazy_bird.crud import conversation as conversation_crud
    from lazy_bird.crud import message as message_crud
    from lazy_bird.crud import session as session_crud

    conversation = conversation_crud.get(conversation_id)
    if not conversation.runnable:
        raise ConflictError("The conversation waits for a user message.", code="nothing_to_answer")
    with _claim(conversation_id, emit or Emitter()) as run:
        turn = _Turn(conversation_id, run)
        try:
            agent = agent_crud.get(conversation.agent_id)
            runtime = build(agent, session_crud.meta_of(agent.session_id), emitter=run)
            resolved = resolve_for_agent(agent.meta)
        except AppError as error:
            return turn.fail(error.code, error.message, error.details)
        for _ in range(max_iter):
            if run.stopped:
                return turn.finish("stopped")
            pending = conversation_crud.pending_tool_calls(message_crud.for_conversation(conversation_id))
            if pending:
                _run_tools(turn, runtime, pending)
                continue
            if agent.hooks:
                turn.status("running_hooks")
                try:
                    runtime.run_hooks(conversation_id)
                except Exception as error:
                    logger.opt(exception=error).warning("A hook of agent {} failed", agent.id)
                    return turn.fail("hook_failed", f"A hook failed: {error}")
            messages = to_chat_messages(message_crud.for_conversation(conversation_id))
            result = _call_engine(turn, resolved, messages, runtime.tools, retry)
            if isinstance(result, RunOutcome):
                return result
            details = {"reasoning": result.reasoning, "model": result.model, "engine": resolved.engine.name}
            if result.tool_calls and not result.stopped:
                calls = [call.as_dict() for call in result.tool_calls]
                turn.store("tool-calling", result.content or None, {**details, "tool_calls": calls})
                _run_tools(turn, runtime, calls)
                continue
            turn.store("assistant", result.content, {**details, "usage": result.usage, "stopped": result.stopped})
            return turn.finish("stopped" if result.stopped else "completed")
        return turn.fail("max_iterations", f"The agent did not finish within {max_iter} steps.", {"max_iter": max_iter})


class _Relay(Emitter):
    """Forwards a sub-agent's activity to its parent's run; stops when the parent stops."""

    def __init__(self, parent: Emitter, agent_id: int, conversation_id: int) -> None:
        self.parent = parent
        self.scope = {"agent_id": agent_id, "conversation_id": conversation_id}

    def token(self, text: str) -> None:
        self.parent.event({"type": "delegation", **self.scope, "event": {"type": "token", "delta": text}})

    def reasoning(self, text: str) -> None:
        self.parent.event({"type": "delegation", **self.scope, "event": {"type": "reasoning", "delta": text}})

    def event(self, payload: dict[str, Any]) -> None:
        self.parent.event({"type": "delegation", **self.scope, "event": payload})

    @property
    def stopped(self) -> bool:
        return self.parent.stopped


def delegate(parent, child, task: str, emitter: Emitter | None = None) -> str:
    """Run ``child`` on ``task`` in a new conversation and return its final answer."""
    from lazy_bird.crud import conversation as conversation_crud

    if not task.strip():
        raise InvalidInputError("The delegated task is empty.", code="empty_task")
    conversation = conversation_crud.create(child.id, title=f"Task from {parent.name}")
    conversation_crud.add_user_message(conversation.id, task)
    parent_emit = emitter or Emitter()
    parent_emit.event({"type": "status", "state": "delegating", "agent": child.name, "conversation_id": conversation.id})
    outcome = agentic_loop(conversation.id, emit=_Relay(parent_emit, child.id, conversation.id))
    answer = outcome.answer
    if outcome.reason == "completed" and answer is not None:
        return answer.content or ""
    reason = answer.content if answer is not None else outcome.reason
    raise AppError(f"{child.name} could not finish the task: {reason}", code="delegation_failed", details={"conversation_id": conversation.id})


def complete(prompt: str, instructions: str | None = None, preset_id: int | None = None) -> ChatResult:
    """One question, one answer, with an inference preset (the default one when omitted)."""
    resolved = engine_family.resolve(preset_id)
    messages = ([ChatMessage("system", instructions)] if instructions else []) + [ChatMessage("user", prompt)]
    return resolved.module.chat(messages, [], resolved.settings, resolved.model, Emitter())


__all__ = [
    "CallbackEmitter",
    "ChatMessage",
    "ChatResult",
    "Emitter",
    "EngineError",
    "RunOutcome",
    "agent_meta",
    "agentic_loop",
    "complete",
    "delegate",
    "engine_family",
    "is_running",
    "resolve_for_agent",
    "stop",
]
