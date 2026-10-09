"""A tiny local inference engine for testing host processes: importable by name, so a child process can load it.

It streams its answer word by word, and says in ``ChatResult.model`` which process answered.
"""

import os
import time

from pydantic import BaseModel, ConfigDict

from lazy_bird.inference.types import ChatResult, EngineError

name = "hosted-chat"
local = True


class EngineSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = "hello from the host"
    gpu_mb: float = 0
    until_stopped: bool = False  # stream one word, then go on until the emitter is stopped
    error_code: str | None = None  # raise an EngineError with this code (not retryable)


def placements(settings, model):
    return [({"device": "gpu"}, {"vram_mb": settings.gpu_mb})] if settings.gpu_mb else []


def load(settings, model):
    return {"pid": os.getpid()}


def unload(instance):
    pass


def chat(instance, messages, tools, settings, model, emit):
    if settings.error_code:
        raise EngineError("The model refused (pretend).", code=settings.error_code, retryable=False)
    process = str(instance["pid"])
    if settings.until_stopped:
        emit.token("thinking")
        deadline = time.monotonic() + 20
        while not emit.stopped and time.monotonic() < deadline:
            time.sleep(0.02)
        return ChatResult(content="thinking", model=process, stopped=emit.stopped)
    emit.reasoning("pondering")
    for word in settings.answer.split(" "):
        emit.token(f"{word} ")
    return ChatResult(content=settings.answer, model=process)
