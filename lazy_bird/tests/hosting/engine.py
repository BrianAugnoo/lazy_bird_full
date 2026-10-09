"""A tiny local engine for testing host processes: importable by name, so a child process can load it.

Its "model" is the pid of the process holding it, which tells where it lives.
"""

import os
import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict

name = "hosted-fake"
local = True


class EngineSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: int = 4
    device: str | None = None
    gpu_mb: float = 0
    cpu_mb: float = 0
    marker: str | None = None  # file written by unload(): proves where it ran
    fail_load: bool = False


def vector_space(settings):
    return f"hosted/space-{settings.dimension}"


def load_key(settings, model):
    return settings.dimension, settings.device


def placements(settings, model):
    plans = []
    if settings.gpu_mb and settings.device in (None, "gpu"):
        plans.append(({"device": "gpu"}, {"vram_mb": settings.gpu_mb}))
    if settings.cpu_mb and settings.device in (None, "cpu"):
        plans.append(({"device": "cpu"}, {"ram_mb": settings.cpu_mb}))
    return plans


def load(settings, model):
    if settings.fail_load:
        raise MemoryError("CUDA out of memory (pretend)")
    return {"pid": os.getpid(), "marker": settings.marker}


def unload(instance):
    if instance["marker"]:
        Path(instance["marker"]).write_text(str(os.getpid()))


def embed(instance, texts, settings, model):
    return [[float(instance["pid"]), float(len(text))] for text in texts]


def fail(instance, settings, model):
    raise ValueError("bad input")


def crash(instance, settings, model):
    os._exit(3)


def sleep(instance, seconds, settings, model):
    time.sleep(seconds)
    return instance["pid"]
