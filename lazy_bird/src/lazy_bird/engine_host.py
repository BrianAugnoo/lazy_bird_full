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
- ``("stats",)``                   -> GPU memory the process uses (its RAM is read by the server);
- ``("stop",)``                    -> the module's ``unload`` runs, then the process exits.

Every answer is ``("ok", value)`` or ``("error", {type, message, traceback, ...})``.
Operations take and return values that can be pickled, except an ``Emitter`` (the chat
of an inference engine): it is replaced by a relay in the process, so while the call runs
the process sends ``("token", text)``, ``("reasoning", text)`` and ``("event", payload)``,
which the server hands to the real emitter, and the server sends ``("stop_call",)`` once
the emitter is stopped, which turns the relay's ``stopped`` on. The connection closing
(the server died) ends the process.
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

STREAMED = ("token", "reasoning", "event")  # what an operation sends through its emitter while it runs
STOP_POLL_SECONDS = 0.1  # how often a streaming call checks whether its emitter was stopped


class EngineProcessError(ProcessFailed):
    """The host process of an engine failed: an operation raised in it, or the process is gone."""

    code = "engine_failed"


class EmitterSlot:
    """Where an operation's emitter goes in the arguments sent to a host (the process puts its relay there)."""


def _remote_error(payload: dict[str, Any]) -> Exception:
    """The error an operation raised in its process, as the server raises it."""
    details = {**payload.get("details", {}), "type": payload["type"], "traceback": payload["traceback"]}
    if payload.get("retryable") is not None:  # an engine's own EngineError: retried by the agentic loop as it says
        from lazy_bird.inference.types import EngineError

        return EngineError(payload["message"], code=payload.get("code"), retryable=payload["retryable"], details=details)
    return EngineProcessError(payload["message"], code=payload.get("code", EngineProcessError.code), details=details)


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
        """Run ``module.<operation>(instance, *args)`` in the process and return its result.

        An ``Emitter`` among ``args`` receives what the operation streams, and stopping it
        asks the operation to stop (it sees its emitter's ``stopped`` turn on).
        """
        from lazy_bird.inference.types import Emitter

        emit = next((arg for arg in args if isinstance(arg, Emitter)), None)
        if emit is None:
            return self._ask(("call", operation, args))
        sent = tuple(EmitterSlot() if arg is emit else arg for arg in args)
        return self._ask(("call", operation, sent), emit=emit)

    def stats(self) -> dict[str, float] | None:
        """Memory the process uses, or None when it is gone: ``rss_mb`` and, when it uses the
        GPU, ``vram_mb`` (now) and ``vram_peak_mb`` (the most it took, e.g. during a batch).

        GPU memory is asked to the process, only when it is not busy with a call.
        """
        if not self.alive:
            return None
        used = {"rss_mb": self._child.memory_mb() or 0.0}
        try:
            used.update(self._ask(("stats",), timeout=5, blocking=False) or {})
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

    def _ask(self, request: tuple, timeout: float | None = None, emit: Any = None, *, blocking: bool = True) -> Any:
        connection = self._child.connection
        # Stats must acquire and use the same lock in one step: probing and
        # releasing it first lets a long model call slip in before the request.
        if not self._exchange.acquire(blocking=blocking):
            return None
        try:
            try:
                connection.send(request)
                stop_sent = False
                while True:
                    if emit is not None:  # stream: relay what comes, and the stop when it is asked
                        if emit.stopped and not stop_sent:
                            connection.send(("stop_call",))
                            stop_sent = True
                        if not connection.poll(STOP_POLL_SECONDS):
                            continue
                    elif timeout is not None and not connection.poll(timeout):
                        self.kill()  # a late answer would be taken for the next one: the process cannot be reused
                        raise EngineProcessError(f"The engine process did not answer within {timeout:g} s and was ended.", code="engine_timeout")
                    status, value = connection.recv()
                    if status not in STREAMED:
                        break
                    try:
                        getattr(emit, status)(value)
                    except Exception:
                        # Leaving now would leave the rest of the stream to be read as the next answer.
                        logger.exception("The emitter of a call to engine host {} failed: the call is stopped", self.pid)
                        if not stop_sent:
                            connection.send(("stop_call",))
                            stop_sent = True
            except (EOFError, OSError):
                self._child.wait(1)
                code = self._child.exit_code
                raise EngineProcessError(
                    f"The engine process stopped unexpectedly (exit code {code}); it may have run out of memory.",
                    code="engine_crashed",
                    details={"exit_code": code},
                ) from None
        finally:
            self._exchange.release()
        if status == "error":
            raise _remote_error(value)
        return value


# ------------------------------------------------------------------ child side
# The CUDA context of the process, which torch's allocator does not count: measured at
# 110-150 MB (CUDA 12.8, lazy module loading), growing as kernels are loaded.
CUDA_CONTEXT_MB = 200


def _gpu_memory_used() -> dict[str, float]:
    """GPU memory of this process: now (``vram_mb``) and the most it took (``vram_peak_mb``), context included."""
    torch = sys.modules.get("torch")
    if torch is not None and torch.cuda.is_available() and torch.cuda.is_initialized():
        return {
            "vram_mb": torch.cuda.memory_reserved() / 1024**2 + CUDA_CONTEXT_MB,
            "vram_peak_mb": torch.cuda.max_memory_reserved() / 1024**2 + CUDA_CONTEXT_MB,
        }
    return {}


class _RelayedEmitter:
    """In the host: the emitter of the server's call (the ``Emitter`` interface), reached over the connection.

    During a call the server sends nothing but ``("stop_call",)``, so ``stopped`` can read it.
    """

    def __init__(self, connection) -> None:
        self._connection = connection
        self._lock = threading.Lock()  # an engine may stream from threads of its own
        self._stopped = False

    def token(self, text: str) -> None:
        self._send("token", text)

    def reasoning(self, text: str) -> None:
        self._send("reasoning", text)

    def event(self, payload: dict[str, Any]) -> None:
        self._send("event", payload)

    def _send(self, kind: str, value: Any) -> None:
        with self._lock:
            self._connection.send((kind, value))

    @property
    def stopped(self) -> bool:
        with self._lock:
            while not self._stopped and self._connection.poll():
                self._stopped = self._connection.recv()[0] == "stop_call"
        return self._stopped


def _with_relay(args: tuple, connection) -> tuple:
    """The arguments of a call, with the server's emitter (``EmitterSlot``) replaced by a relay to it."""
    if not any(isinstance(arg, EmitterSlot) for arg in args):
        return args
    relay = _RelayedEmitter(connection)
    return tuple(relay if isinstance(arg, EmitterSlot) else arg for arg in args)


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
            if kind == "stop_call":
                continue  # asked as the last call was ending: nothing left to stop
            try:
                if kind == "load":
                    instance, loaded = module.load(request[1], request[2]), True
                    answer = None
                elif kind == "call":
                    answer = getattr(module, request[1])(instance, *_with_relay(request[2], connection))
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
    # Serve from the module under its own name: what the server pickles (an EmitterSlot)
    # comes back as lazy_bird.engine_host's classes, not this __main__ copy's.
    from lazy_bird.engine_host import serve as serve_by_name

    serve_by_name()
