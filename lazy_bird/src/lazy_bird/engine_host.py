"""Host processes: a local engine's model lives in a child process of its own.

Why: a model unloaded inside the server never gives back all its memory (the CUDA
context and the allocator keep some), a crash or an out-of-memory kill takes the whole
server with it, and a thread cannot be stopped. A process can: when it exits the
operating system takes everything back, and it can be killed.

``EngineHost`` (server side) starts ``python -m lazy_bird.engine_host`` for one engine
module, which imports the module by name and then serves requests on a private,
authenticated connection, one at a time:

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
import os
import secrets
import subprocess
import sys
import threading
import traceback
from multiprocessing.connection import Client, Connection, Listener
from types import ModuleType
from typing import Any

from loguru import logger

from lazy_bird.errors import AppError

KEY_VARIABLE = "LAZY_BIRD_HOST_KEY"
START_TIMEOUT_SECONDS = 120  # importing torch and loading a large model takes a while
STOP_TIMEOUT_SECONDS = 15


class EngineProcessError(AppError):
    """The host process of an engine failed: an operation raised in it, or the process is gone."""

    status_code = 502
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

    def __init__(self, process: subprocess.Popen, connection: Connection, module_name: str) -> None:
        self._process = process
        self._connection = connection
        self.module_name = module_name
        self._exchange = threading.Lock()  # one request/answer at a time on the connection
        self.stopped = False

    @classmethod
    def start(cls, module_name: str, settings: Any, model: Any) -> EngineHost:
        """Start a host for ``module_name`` and load the model in it (raises ``EngineProcessError``)."""
        key = secrets.token_bytes(16)
        listener = Listener(("127.0.0.1", 0), authkey=key)
        host, port = listener.address
        environment = {**os.environ, KEY_VARIABLE: key.hex(), "PYTHONPATH": os.pathsep.join(path for path in sys.path if path)}
        process = subprocess.Popen(
            [sys.executable, "-m", "lazy_bird.engine_host", host, str(port), module_name], env=environment, stdin=subprocess.DEVNULL
        )
        try:
            connection = cls._accept(listener, process)
        finally:
            listener.close()
        engine = cls(process, connection, module_name)
        try:
            engine._ask(("load", settings, model), timeout=START_TIMEOUT_SECONDS)
        except BaseException:
            engine.kill()
            raise
        logger.info("Engine host {} started for {}", process.pid, module_name)
        return engine

    @staticmethod
    def _accept(listener: Listener, process: subprocess.Popen) -> Connection:
        accepted: list[Connection] = []

        def accept() -> None:
            try:
                accepted.append(listener.accept())
            except OSError:
                pass  # the listener was closed because the process never connected

        thread = threading.Thread(target=accept, daemon=True)
        thread.start()
        waited = 0.0
        while thread.is_alive() and waited < START_TIMEOUT_SECONDS:
            thread.join(0.1)
            waited += 0.1
            if process.poll() is not None and thread.is_alive():
                break
        if not accepted:
            process.kill()
            raise EngineProcessError(
                f"The engine process could not start (exit code {process.poll()}). See the server log.", code="engine_start_failed"
            )
        return accepted[0]

    @property
    def pid(self) -> int:
        return self._process.pid

    @property
    def alive(self) -> bool:
        return not self.stopped and self._process.poll() is None

    def call(self, operation: str, args: tuple) -> Any:
        """Run ``module.<operation>(instance, *args)`` in the process and return its result."""
        return self._ask(("call", operation, args))

    def stats(self) -> dict[str, float] | None:
        """Memory the process uses, or None when it is busy with a call or gone."""
        if not self.alive or not self._exchange.acquire(blocking=False):
            return None
        self._exchange.release()
        try:
            return self._ask(("stats",), timeout=5)
        except EngineProcessError:
            return None

    def stop(self) -> None:
        """Ask the module to unload, then end the process; kill it if it does not end in time."""
        if self.stopped:
            return
        try:
            if self._process.poll() is None:
                self._ask(("stop",), timeout=STOP_TIMEOUT_SECONDS)
                self._process.wait(STOP_TIMEOUT_SECONDS)
        except BaseException as error:
            logger.warning("Engine host {} did not stop cleanly ({}): killing it", self.pid, error)
        finally:
            self.kill()

    def kill(self) -> None:
        """End the process now. A call in progress fails; the memory of the process is returned to the system."""
        self.stopped = True
        if self._process.poll() is None:
            self._process.kill()
        try:
            self._process.wait(STOP_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            logger.error("Engine host {} did not end after being killed", self.pid)
        try:
            self._connection.close()
        except OSError:
            pass

    def _ask(self, request: tuple, timeout: float | None = None) -> Any:
        with self._exchange:
            try:
                self._connection.send(request)
                if timeout is not None and not self._connection.poll(timeout):
                    self.kill()  # a late answer would be taken for the next one: the process cannot be reused
                    raise EngineProcessError(f"The engine process did not answer within {timeout:g} s and was ended.", code="engine_timeout")
                status, value = self._connection.recv()
            except (EOFError, OSError, BrokenPipeError):
                code = self._process.poll()
                raise EngineProcessError(
                    f"The engine process stopped unexpectedly (exit code {code}); it may have run out of memory.",
                    code="engine_crashed",
                    details={"exit_code": code},
                ) from None
        if status == "error":
            raise EngineProcessError(value["message"], details={"type": value["type"], "traceback": value["traceback"]})
        return value


# ------------------------------------------------------------------ child side
def _memory_used() -> dict[str, float]:
    import psutil

    used = {"rss_mb": psutil.Process().memory_info().rss / 1024**2}
    torch = sys.modules.get("torch")
    if torch is not None and torch.cuda.is_available() and torch.cuda.is_initialized():
        used["vram_mb"] = torch.cuda.memory_reserved() / 1024**2
    return used


def serve(host: str, port: int, module_name: str) -> None:
    """Child process entry point: import the engine module and serve the server's requests."""
    module = importlib.import_module(module_name)
    connection = Client((host, port), authkey=bytes.fromhex(os.environ.pop(KEY_VARIABLE)))
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
                    answer = _memory_used()
                else:  # stop
                    break
                connection.send(("ok", answer))
            except BaseException as error:
                if isinstance(error, (KeyboardInterrupt, SystemExit)):
                    raise
                connection.send(("error", {"type": type(error).__name__, "message": str(error) or type(error).__name__, "traceback": traceback.format_exc()}))
        if loaded:
            module.unload(instance)
        connection.send(("ok", None))
    finally:
        connection.close()


if __name__ == "__main__":
    serve(sys.argv[1], int(sys.argv[2]), sys.argv[3])
