"""Isolated task kinds for the tests: declared at module level so a task process can import them.

Gates are files (threading events do not cross processes): a step waits until ``<gate_dir>/<name>`` exists.
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from lazy_bird.crud import task as task_crud
from lazy_bird.embedding import engine_family
from lazy_bird.errors import InvalidInputError
from lazy_bird.tasks import TaskContext, task


def _wait(gate_dir: str, name: str, ctx: TaskContext | None = None, timeout: float = 20) -> None:
    deadline = time.monotonic() + timeout
    while not (Path(gate_dir) / name).exists():
        if time.monotonic() > deadline:
            raise TimeoutError(f"gate {name} never opened")
        if ctx is not None:
            ctx.checkpoint(message=f"waiting for {name}")
        time.sleep(0.02)


@task("test.isolated.where", title="Where am I", isolated=True)
def where(ctx: TaskContext, label: str) -> dict:
    """Reports progress, reads its own row from the database and says which process ran it."""
    ctx.report(0.5, "halfway")
    ctx.checkpoint(0.9, "almost", state={"seen": label})
    return {"pid": os.getpid(), "title": task_crud.get(ctx.task_id).title, "label": label}


@task("test.isolated.steps", title="Steps {name}", isolated=True)
def steps(ctx: TaskContext, name: str, gate_dir: str, count: int = 3) -> dict:
    """Does ``count`` steps, each waiting for the gate ``<name>-<step>`` and saving its progress."""
    pids = list(ctx.state.get("pids", [])) + [os.getpid()]
    for index in range(ctx.state.get("done", 0), count):
        _wait(gate_dir, f"{name}-{index}", ctx)
        ctx.checkpoint((index + 1) / count, f"step {index}", state={"done": index + 1, "pids": pids})
    return {"pids": pids}


@task("test.isolated.stuck", title="Stuck {name}", isolated=True)
def stuck(ctx: TaskContext, name: str, gate_dir: str) -> int:
    """Writes its pid then sleeps without ever reaching a checkpoint."""
    (Path(gate_dir) / f"{name}.pid").write_text(str(os.getpid()))
    time.sleep(60)
    return os.getpid()


@task("test.isolated.crash", title="Crash", isolated=True)
def crash(ctx: TaskContext) -> None:
    os._exit(7)


@task("test.isolated.refuse", title="Refuse", isolated=True)
def refuse(ctx: TaskContext) -> None:
    raise InvalidInputError("This input cannot be processed.", code="bad_input", details={"why": "test"})


@task("test.isolated.embed", title="Embed with {engine_id}", isolated=True, engines=lambda engine_id, settings: [engine_family.resolve_settings(engine_id, settings)])
def embed(ctx: TaskContext, engine_id: int, settings: dict) -> dict:
    """Uses a local model: the call goes to the server, whose residency holds the model."""
    resolved = engine_family.resolve_settings(engine_id, settings)
    with resolved.loaded():
        [[model_pid, length]] = resolved.call("embed", ["abc"])
    return {"pid": os.getpid(), "model_pid": model_pid, "length": length}


@task("test.isolated.blocking", title="Blocking {name}", isolated=True)
def blocking(ctx: TaskContext, name: str, gate_dir: str) -> None:
    """Waits for a call that never reaches a checkpoint, run by a thread pool (like a Hugging Face download)."""
    (Path(gate_dir) / f"{name}.pid").write_text(str(os.getpid()))
    ctx.run_blocking(ThreadPoolExecutor(1).submit(time.sleep, 60).result)
