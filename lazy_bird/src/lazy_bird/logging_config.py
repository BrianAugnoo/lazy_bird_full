from __future__ import annotations

import inspect
import logging
import sys
from threading import local
from functools import wraps
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, ParamSpec, TypeVar, cast

from loguru import logger


P = ParamSpec("P")
R = TypeVar("R")


class _InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.opt(exception=record.exc_info, depth=6).log(level, record.getMessage())


class _StreamToLoguru:
    def __init__(self, level: str) -> None:
        self.level = level
        self._state = local()

    def write(self, message: str) -> int:
        if getattr(self._state, "writing", False):
            return sys.__stderr__.write(message)
        message = message.rstrip()
        if message:
            self._state.writing = True
            try:
                logger.opt(depth=6).log(self.level, message)
            finally:
                self._state.writing = False
        return len(message)

    def flush(self) -> None:
        return None


def _console_sink(message: str) -> None:
    try:
        sys.__stdout__.write(message)
        sys.__stdout__.flush()
    except OSError:
        return None


def configure_logging(log_file: str | Path = "logs.txt") -> None:
    """Install the application-wide Loguru sinks and stdlib bridge once."""
    if getattr(configure_logging, "configured", False):
        return

    logger.remove()
    logger.add(
        _console_sink,
        level="DEBUG",
        colorize=True,
        diagnose=True,
        backtrace=True,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{process.name}:{process.id}</cyan> | "
            "<magenta>{thread.name}:{thread.id}</magenta> | "
            "<blue>{name}:{function}:{line}</blue> | <level>{message}</level>"
        ),
    )
    logger.add(
        Path(log_file),
        level="DEBUG",
        colorize=False,
        diagnose=True,
        backtrace=True,
        rotation="10 MB",
        retention=5,
        encoding="utf-8",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
            "{process.name}:{process.id} | {thread.name}:{thread.id} | "
            "{name}:{function}:{line} | {message}"
        ),
    )

    intercept_handler = _InterceptHandler()
    logging.basicConfig(handlers=[intercept_handler], level=logging.DEBUG, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        logging.getLogger(name).handlers = [intercept_handler]
        logging.getLogger(name).propagate = False

    sys.stdout = _StreamToLoguru("INFO")  # type: ignore[assignment]
    sys.stderr = _StreamToLoguru("ERROR")  # type: ignore[assignment]
    configure_logging.configured = True
    logger.info("Logging configured: diagnose=True, log_file={}", Path(log_file).resolve())


def traced(func: Callable[P, R]) -> Callable[P, R]:
    """Log function calls, arguments, return values, failures, and duration."""
    module = func.__module__
    function_name = func.__qualname__

    if inspect.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            started = perf_counter()
            logger.info(
                "CALL function {} on module {} with args={} kwargs={}",
                function_name,
                module,
                args,
                kwargs,
            )
            try:
                result = await func(*args, **kwargs)  # type: ignore[misc]
                logger.info(
                    "RETURN function {} on module {} -> {} | status=success duration_ms={:.2f}",
                    function_name,
                    module,
                    result,
                    (perf_counter() - started) * 1000,
                )
                return result
            except Exception:
                logger.opt(exception=True).exception(
                    "ERROR function {} on module {} | status=error duration_ms={:.2f}",
                    function_name,
                    module,
                    (perf_counter() - started) * 1000,
                )
                raise

        return cast(Callable[P, R], async_wrapper)

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        started = perf_counter()
        logger.info(
            "CALL function {} on module {} with args={} kwargs={}",
            function_name,
            module,
            args,
            kwargs,
        )
        try:
            result = func(*args, **kwargs)
            logger.info(
                "RETURN function {} on module {} -> {} | status=success duration_ms={:.2f}",
                function_name,
                module,
                result,
                (perf_counter() - started) * 1000,
            )
            return result
        except Exception:
            logger.opt(exception=True).exception(
                "ERROR function {} on module {} | status=error duration_ms={:.2f}",
                function_name,
                module,
                (perf_counter() - started) * 1000,
            )
            raise

    return wrapper


trace = traced