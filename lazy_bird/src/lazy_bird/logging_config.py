from __future__ import annotations

import inspect
import json
import logging
import sys
import threading
from functools import wraps
from pathlib import Path
from time import perf_counter
from contextvars import ContextVar
from threading import local
from typing import Any, Callable, ParamSpec, TypeVar, cast
from uuid import uuid4

from loguru import logger


P = ParamSpec("P")
R = TypeVar("R")
_trace_stack: ContextVar[tuple[str, ...]] = ContextVar("lazy_bird_trace_stack", default=())
_traced_codes: set[Any] = set()
_trace_profile_enabled = False
_profile_state = local()


def _safe_repr(value: Any) -> str:
    try:
        return repr(value)
    except Exception as exc:
        return f"<unrepresentable {type(value).__name__}: {exc}>"


def _event_message(event: str, **values: Any) -> str:
    return json.dumps({"event": event, **values}, ensure_ascii=True, separators=(",", ":"), default=_safe_repr)


def _log_event(event: str, *, exception: Any = None, **values: Any) -> None:
    message = _event_message(event, **values)
    if exception is not None:
        logger.opt(exception=exception).error(message)
    else:
        logger.info(message)


def _function_arguments(frame: Any) -> dict[str, str]:
    try:
        arguments = inspect.getargvalues(frame)
        values = {name: arguments.locals[name] for name in arguments.args}
        if arguments.varargs:
            values[arguments.varargs] = arguments.locals.get(arguments.varargs, ())
        if arguments.keywords:
            values.update(arguments.locals.get(arguments.keywords, {}))
        return {name: _safe_repr(value) for name, value in values.items()}
    except Exception as exc:
        return {"<error>": _safe_repr(exc)}


def _is_lazy_bird_frame(frame: Any) -> bool:
    module = frame.f_globals.get("__name__") or ""
    return module.startswith("lazy_bird.") and module != "lazy_bird.logging_config"


def _profile_function(frame: Any, event: str, argument: Any) -> None:
    if not _trace_profile_enabled or not _is_lazy_bird_frame(frame):
        return

    state = getattr(_profile_state, "calls", None)
    if state is None:
        state = []
        _profile_state.calls = state
    frame_id = id(frame)

    if event == "call":
        if frame.f_code in _traced_codes:
            return
        call_id = uuid4().hex
        parent_id = _trace_stack.get()[-1] if _trace_stack.get() else None
        state.append([frame_id, call_id, perf_counter(), None])
        _trace_stack.set((*_trace_stack.get(), call_id))
        _log_event(
            "function_call",
            call_id=call_id,
            parent_id=parent_id,
            module=frame.f_globals.get("__name__"),
            function=frame.f_code.co_qualname,
            args=_function_arguments(frame),
        )
    elif event == "exception":
        for index in range(len(state) - 1, -1, -1):
            if state[index][0] == frame_id:
                state[index][3] = argument
                break
    elif event == "return":
        for index in range(len(state) - 1, -1, -1):
            if state[index][0] == frame_id:
                _, call_id, started, exception_info = state.pop(index)
                stack = _trace_stack.get()
                if stack and stack[-1] == call_id:
                    _trace_stack.set(stack[:-1])
                _log_event(
                    "function_return",
                    exception=exception_info,
                    call_id=call_id,
                    parent_id=_trace_stack.get()[-1] if _trace_stack.get() else None,
                    module=frame.f_globals.get("__name__"),
                    function=frame.f_code.co_qualname,
                    status="error" if exception_info else "success",
                    duration_ms=round((perf_counter() - started) * 1000, 2),
                    result=_safe_repr(argument),
                )
                break


def set_package_tracing(enabled: bool) -> None:
    """Trace every Python function executed by the lazy_bird package."""
    global _trace_profile_enabled
    _trace_profile_enabled = enabled
    sys.setprofile(_profile_function if enabled else None)
    threading.setprofile(_profile_function if enabled else None)


class _InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.opt(exception=record.exc_info, depth=6).log(level, record.getMessage())


class _StreamToLoguru:
    """File-like object turning ``print``/``sys.stderr`` output into log records.

    ``print("a", b)`` issues several ``write`` calls; text is buffered per thread
    until a newline so that one printed line becomes one log record.
    """

    def __init__(self, level: str) -> None:
        self.level = level
        self._state = local()

    def write(self, message: str) -> int:
        if getattr(self._state, "writing", False):
            return sys.__stderr__.write(message)
        buffered = getattr(self._state, "buffer", "") + message
        *lines, rest = buffered.split("\n")
        self._state.buffer = rest
        for line in lines:
            self._emit(line)
        return len(message)

    def _emit(self, line: str) -> None:
        line = line.rstrip()
        if not line:
            return
        self._state.writing = True
        try:
            logger.opt(depth=7).log(self.level, line)
        finally:
            self._state.writing = False

    def flush(self) -> None:
        rest = getattr(self._state, "buffer", "")
        self._state.buffer = ""
        self._emit(rest)


def _console_sink(message: str) -> None:
    try:
        sys.__stdout__.write(message)
        sys.__stdout__.flush()
    except OSError:
        return None


LOG_FILE = Path("logs.txt").resolve()


def tracing_enabled() -> bool:
    return _trace_profile_enabled


def configure_logging(log_file: str | Path = "logs.txt", trace_all: bool = False) -> None:
    """Install the application-wide Loguru sinks and stdlib bridge once."""
    global LOG_FILE
    if getattr(configure_logging, "configured", False):
        return
    LOG_FILE = Path(log_file).resolve()

    logger.remove()
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{process.name}:{process.id}</cyan> | "
        "<magenta>{thread.name}:{thread.id}</magenta> | "
        "<blue>{name}:{function}:{line}</blue> | <level>{message}</level>"
    )
    logger.add(
        _console_sink,
        level="DEBUG",
        colorize=True,
        diagnose=True,
        backtrace=True,
        format=log_format,
    )
    logger.add(
        Path(log_file),
        level="DEBUG",
        colorize=True,
        diagnose=True,
        backtrace=True,
        rotation="10 MB",
        retention=5,
        encoding="utf-8",
        format=log_format,
    )

    intercept_handler = _InterceptHandler()
    logging.basicConfig(handlers=[intercept_handler], level=logging.DEBUG, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        logging.getLogger(name).handlers = [intercept_handler]
        logging.getLogger(name).propagate = False

    sys.stdout = _StreamToLoguru("INFO")  # type: ignore[assignment]
    sys.stderr = _StreamToLoguru("ERROR")  # type: ignore[assignment]
    configure_logging.configured = True
    _log_event("logging_configured", diagnose=True, trace_all=trace_all, log_file=str(Path(log_file).resolve()))
    set_package_tracing(trace_all)


def traced(func: Callable[P, R]) -> Callable[P, R]:
    """Log function calls, arguments, return values, failures, and duration."""
    module = func.__module__
    function_name = func.__qualname__

    _traced_codes.add(func.__code__)

    def log_call(call_id: str, parent_id: str | None, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        _log_event(
            "function_call",
            call_id=call_id,
            parent_id=parent_id,
            module=module,
            function=function_name,
            args={"positional": _safe_repr(args), "keyword": _safe_repr(kwargs)},
        )

    def log_return(call_id: str, parent_id: str | None, started: float, result: Any) -> None:
        _log_event(
            "function_return",
            call_id=call_id,
            parent_id=parent_id,
            module=module,
            function=function_name,
            status="success",
            duration_ms=round((perf_counter() - started) * 1000, 2),
            result=_safe_repr(result),
        )

    def log_error(call_id: str, parent_id: str | None, started: float) -> None:
        _log_event(
            "function_return",
            exception=True,
            call_id=call_id,
            parent_id=parent_id,
            module=module,
            function=function_name,
            status="error",
            duration_ms=round((perf_counter() - started) * 1000, 2),
        )

    if inspect.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            started = perf_counter()
            call_id = uuid4().hex
            parent_id = _trace_stack.get()[-1] if _trace_stack.get() else None
            token = _trace_stack.set((*_trace_stack.get(), call_id))
            log_call(call_id, parent_id, args, kwargs)
            try:
                result = await func(*args, **kwargs)  # type: ignore[misc]
                log_return(call_id, parent_id, started, result)
                return result
            except Exception:
                log_error(call_id, parent_id, started)
                raise
            finally:
                _trace_stack.reset(token)

        _traced_codes.add(async_wrapper.__code__)
        return cast(Callable[P, R], async_wrapper)

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        started = perf_counter()
        call_id = uuid4().hex
        parent_id = _trace_stack.get()[-1] if _trace_stack.get() else None
        token = _trace_stack.set((*_trace_stack.get(), call_id))
        log_call(call_id, parent_id, args, kwargs)
        try:
            result = func(*args, **kwargs)
            log_return(call_id, parent_id, started, result)
            return result
        except Exception:
            log_error(call_id, parent_id, started)
            raise
        finally:
            _trace_stack.reset(token)

    _traced_codes.add(wrapper.__code__)
    return wrapper


trace = traced