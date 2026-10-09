"""Host processes: a local engine's model lives in a child process of its own.

Why: a model unloaded inside the server never gives back all its memory (the CUDA
context and the allocator keep some), a crash or an out-of-memory kill takes the whole
server with it, and a thread cannot be stopped. A process can: when it exits the
operating system takes everything back, and it can be killed.

``EngineHost`` (server side) starts ``python -m lazy_bird.engine_host`` for one engine
module (see ``processes``), which imports the module by name and then serves requests,
one at a time:

- ``("load", settings, model)``    -> the module's ``load`` builds the model, kept in the process;
- ``("call", operation, args)``    -> ``module.<operation>(instance, *args)``;
- ``("stats",)``                   -> memory the process uses;
- ``("stop",)``                    -> the module's ``unload`` runs, then the process exits.

Every answer is ``("ok", value)`` or ``("error", {type, message, traceback})``. Operations
must take and return values that can be pickled (no streaming callbacks yet). The
connection closing (the server died) ends the process.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import threading
from types import ModuleType
from typing import Any

from loguru import logger

from lazy_bird.processes import END_TIMEOUT_SECONDS, START_TIMEOUT_SECONDS, ChildProcess, ProcessFailed, connect_to_parent, error_payload


class EngineProcessError(ProcessFailed):
    """The host process of an engine failed: an operation raised in it, or the process is gone."""

    code = "engine_failed"


def importable(module: ModuleType) -> bool:
    """Whether a child process can import the module by name (engine files are; modules built on the fly are not)."""
    name = getattr(module, "__name__", "")
    try:
        return bool(name) and importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


class EngineHost:
    """The server side of a host process holding one loaded model."""

    def __init__(self, child: ChildProcess, module_name: str) -> None:
        self._child = child
        self.module_name = module_name
        self._exchange = threading.Lock()  # one request/answer at a time on the connection

    @classmethod
    def start(cls, module_name: str, settings: Any, model: Any) -> EngineHost:
        """Start a host for ``module_name`` and load the model in it (raises ``EngineProcessError``)."""
        engine = cls(ChildProcess.start("lazy_bird.engine_host", module_name, error=EngineProcessError), module_name)
        try:
            engine._ask(("load", settings, model), timeout=START_TIMEOUT_SECONDS)
        except BaseException:
            engine.kill()
            raise
        logger.info("Engine host {} started for {}", engine.pid, module_name)
        return engine

    @property
    def pid(self) -> int:
        return self._child.pid

    @property
    def alive(self) -> bool:
        return self._child.alive

    def call(self, operation: str, args: tuple) -> Any:
        """Run ``module.<operation>(instance, *args)`` in the process and return its result."""
        return self._ask(("call", operation, args))

    def stats(self) -> dict[str, float] | None:
        """Memory the process uses (``rss_mb``, ``vram_mb`` when it uses the GPU), or None when it is gone.

        GPU memory is asked to the process, only when it is not busy with a call.
        """
        if not self.alive:
            return None
        used = {"rss_mb": self._child.memory_mb() or 0.0}
        if self._exchange.acquire(blocking=False):
            self._exchange.release()
            try:
                used.update(self._ask(("stats",), timeout=5))
            except EngineProcessError:
                pass
        return used

    def stop(self) -> None:
        """Ask the module to unload, then end the process; kill it if it does not end in time."""
        if self._child.ended:
            return
        try:
            if self._child.alive:
                self._ask(("stop",), timeout=END_TIMEOUT_SECONDS)
                self._child.wait(END_TIMEOUT_SECONDS)
        except BaseException as error:
            logger.warning("Engine host {} did not stop cleanly ({}): killing it", self.pid, error)
        finally:
            self.kill()

    def kill(self) -> None:
        """End the process now. A call in progress fails; the memory of the process is returned to the system."""
        self._child.kill()

    def _ask(self, request: tuple, timeout: float | None = None) -> Any:
        connection = self._child.connection
        with self._exchange:
            try:
                connection.send(request)
                if timeout is not None and not connection.poll(timeout):
                    self.kill()  # a late answer would be taken for the next one: the process cannot be reused
                    raise EngineProcessError(f"The engine process did not answer within {timeout:g} s and was ended.", code="engine_timeout")
                status, value = connection.recv()
            except (EOFError, OSError):
                self._child.wait(1)
                code = self._child.exit_code
                raise EngineProcessError(
                    f"The engine process stopped unexpectedly (exit code {code}); it may have run out of memory.",
                    code="engine_crashed",
                    details={"exit_code": code},
                ) from None
        if status == "error":
            raise EngineProcessError(value["message"], details={"type": value["type"], "traceback": value["traceback"]})
        return value


# ------------------------------------------------------------------ child side
def _gpu_memory_used() -> dict[str, float]:
    torch = sys.modules.get("torch")
    if torch is not None and torch.cuda.is_available() and torch.cuda.is_initialized():
        return {"vram_mb": torch.cuda.memory_reserved() / 1024**2}
    return {}


def serve() -> None:
    """Child process entry point: import the engine module and serve the server's requests."""
    connection, (module_name,) = connect_to_parent()
    module = importlib.import_module(module_name)
    instance: Any = None
    loaded = False
    try:
        while True:
            try:
                request = connection.recv()
            except (EOFError, OSError):
                return  # the server is gone
            kind = request[0]
            try:
                if kind == "load":
                    instance, loaded = module.load(request[1], request[2]), True
                    answer = None
                elif kind == "call":
                    answer = getattr(module, request[1])(instance, *request[2])
                elif kind == "stats":
                    answer = _gpu_memory_used()
                else:  # stop
                    break
                connection.send(("ok", answer))
            except (KeyboardInterrupt, SystemExit):
                raise
            except BaseException as error:
                connection.send(("error", error_payload(error)))
        if loaded:
            module.unload(instance)
        connection.send(("ok", None))
    finally:
        connection.close()


if __name__ == "__main__":
    serve()
