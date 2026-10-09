"""Child processes of the server, reached over a private authenticated connection.

Server side: ``ChildProcess.start("lazy_bird.engine_host", "arg")`` runs
``python -m lazy_bird.engine_host <host> <port> arg`` and waits for it to connect back.
Child side: ``connect_to_parent()`` reads the address from its arguments and the key
from its environment. Messages are pickled Python values; the key makes sure only the
child the server started can talk to it.

The child sees the same import paths as the server (``PYTHONPATH``), so it can import
anything the server can, extensions and test modules included.
"""

from __future__ import annotations

import os
import secrets
import subprocess
import sys
import threading
from multiprocessing.connection import Client, Connection, Listener
from typing import Any

from loguru import logger

from lazy_bird.errors import AppError

KEY_VARIABLE = "LAZY_BIRD_CHILD_KEY"
START_TIMEOUT_SECONDS = 120  # importing torch and loading a large model takes a while
END_TIMEOUT_SECONDS = 15


class ProcessFailed(AppError):
    """A child process could not start, failed, or stopped unexpectedly."""

    status_code = 502
    code = "process_failed"


class ChildProcess:
    def __init__(self, process: subprocess.Popen, connection: Connection) -> None:
        self._process = process
        self.connection = connection
        self.ended = False

    @classmethod
    def start(cls, module: str, *arguments: str, error: type[ProcessFailed] = ProcessFailed) -> ChildProcess:
        """Run ``python -m <module>`` and wait until it is connected (``error`` when it never is)."""
        key = secrets.token_bytes(16)
        listener = Listener(("127.0.0.1", 0), authkey=key)
        host, port = listener.address
        environment = {**os.environ, KEY_VARIABLE: key.hex(), "PYTHONPATH": os.pathsep.join(path for path in sys.path if path)}
        python = sys.executable
        base = getattr(sys, "_base_executable", python)
        if sys.platform == "win32" and os.path.normcase(base) != os.path.normcase(python):
            # The python.exe of a Windows virtual environment is a launcher running the real
            # interpreter as its own child: the pid, and the memory read from it, would be the
            # launcher's. Run the interpreter itself in the environment, as multiprocessing does.
            python, environment["__PYVENV_LAUNCHER__"] = base, python
        process = subprocess.Popen([python, "-m", module, host, str(port), *arguments], env=environment, stdin=subprocess.DEVNULL)
        try:
            connection = cls._accept(listener, process)
        finally:
            listener.close()
        if connection is None:
            process.kill()
            process.wait()
            raise error(f"The process could not start (exit code {process.returncode}). See the server log.", code="process_start_failed")
        return cls(process, connection)

    @staticmethod
    def _accept(listener: Listener, process: subprocess.Popen) -> Connection | None:
        accepted: list[Connection] = []

        def accept() -> None:
            try:
                accepted.append(listener.accept())
            except OSError:
                pass  # the listener was closed because the process never connected

        thread = threading.Thread(target=accept, daemon=True)
        thread.start()
        waited = 0.0
        while thread.is_alive() and waited < START_TIMEOUT_SECONDS and process.poll() is None:
            thread.join(0.1)
            waited += 0.1
        thread.join(0.5)  # a connection made just before the process ended still counts
        return accepted[0] if accepted else None

    @property
    def pid(self) -> int:
        return self._process.pid

    @property
    def alive(self) -> bool:
        return not self.ended and self._process.poll() is None

    @property
    def exit_code(self) -> int | None:
        return self._process.poll()

    def memory_mb(self) -> float | None:
        """Resident memory of the process (read from the system, without asking the child)."""
        try:
            import psutil

            return psutil.Process(self.pid).memory_info().rss / 1024**2
        except Exception:
            return None

    def wait(self, timeout: float) -> bool:
        """Whether the process ended within ``timeout``."""
        try:
            self._process.wait(timeout)
            return True
        except subprocess.TimeoutExpired:
            return False

    def kill(self) -> None:
        """End the process now; what it holds goes back to the system. Safe to call again."""
        self.ended = True
        if self._process.poll() is None:
            self._process.kill()
        if not self.wait(END_TIMEOUT_SECONDS):
            logger.error("Process {} did not end after being killed", self.pid)
        try:
            self.connection.close()
        except OSError:
            pass


def connect_to_parent() -> tuple[Connection, list[str]]:
    """In a child process: connect to the server; returns the connection and the extra arguments."""
    host, port, *arguments = sys.argv[1:]
    connection = Client((host, int(port)), authkey=bytes.fromhex(os.environ.pop(KEY_VARIABLE)))
    return connection, arguments


def error_payload(error: BaseException) -> dict[str, Any]:
    """An exception as plain data, to send to the other side."""
    import traceback

    payload = {"type": type(error).__name__, "message": str(error) or type(error).__name__, "traceback": traceback.format_exc()}
    if isinstance(error, AppError):
        payload.update(code=error.code, details=error.details)
    return payload
