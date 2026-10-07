"""Types exchanged between the agentic loop and inference engines.

Engines never see database rows nor WebSockets: they receive ``ChatMessage`` objects
and an ``Emitter``, and return a ``ChatResult``.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from lazy_bird.errors import AppError


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "arguments": self.arguments}


@dataclass(frozen=True)
class ChatMessage:
    """A provider-neutral message, close to the OpenAI chat format."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None
    name: str | None = None


@dataclass
class ChatResult:
    """What an engine returns once generation ends (naturally or because it was stopped)."""

    content: str = ""
    reasoning: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, Any] | None = None
    model: str | None = None
    stopped: bool = False


class EngineError(AppError):
    """An engine failed. ``retryable`` tells the agentic loop whether to try again."""

    status_code = 502
    code = "engine_error"

    def __init__(self, message: str, *, code: str | None = None, retryable: bool = True, details: dict | None = None) -> None:
        super().__init__(message, code=code, details=details)
        self.retryable = retryable


class Emitter:
    """Receives what an engine produces while generating.

    Engines call ``token`` for each piece of answer text and ``reasoning`` for each
    piece of reasoning, and check ``stopped`` regularly: when it becomes true they
    stop generating and return what they have with ``ChatResult.stopped = True``.
    The agentic loop also sends ``event`` notifications (messages stored, status).
    This base class ignores everything; ``CallbackEmitter`` forwards to a function.
    """

    def token(self, text: str) -> None:
        pass

    def reasoning(self, text: str) -> None:
        pass

    def event(self, payload: dict[str, Any]) -> None:
        pass

    @property
    def stopped(self) -> bool:
        return False


class CallbackEmitter(Emitter):
    """Forwards everything as event dicts to ``send``; ``stop()`` asks the engine to stop."""

    def __init__(self, send: Callable[[dict[str, Any]], None]) -> None:
        self._send = send
        self._stop = threading.Event()

    def token(self, text: str) -> None:
        if text:
            self._send({"type": "token", "delta": text})

    def reasoning(self, text: str) -> None:
        if text:
            self._send({"type": "reasoning", "delta": text})

    def event(self, payload: dict[str, Any]) -> None:
        self._send(payload)

    def stop(self) -> None:
        self._stop.set()

    @property
    def stopped(self) -> bool:
        return self._stop.is_set()
