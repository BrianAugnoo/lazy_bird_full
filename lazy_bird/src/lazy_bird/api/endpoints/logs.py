"""Application logs (``logs.txt``): search, call trees and tracing of every call."""

import re
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from lazy_bird import logging_config
from lazy_bird.errors import InvalidInputError, NotFoundError

router = APIRouter(prefix="/logs", tags=["logs"])
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


class LogEntryOut(BaseModel):
    start_line: int
    end_line: int
    timestamp: datetime | None
    level: str | None
    location: str | None
    message: str
    payload: dict[str, Any] | None = None
    score: float | None = None


class TracingIn(BaseModel):
    enabled: bool


def _entry(entry) -> LogEntryOut:
    return LogEntryOut(
        start_line=entry.start_line,
        end_line=entry.end_line,
        timestamp=entry.timestamp,
        level=entry.level,
        location=entry.location,
        message=ANSI.sub("", entry.message or ""),
        payload=entry.payload,
        score=entry.score,
    )


def _log_file():
    if not logging_config.LOG_FILE.exists():
        raise NotFoundError("Log file", str(logging_config.LOG_FILE), code="no_log_file")
    return logging_config.LOG_FILE


@router.get("/", response_model=list[LogEntryOut])
def search_logs(
    query: str | None = None,
    mode: Literal["bm25", "regex"] = "bm25",
    since: datetime | None = None,
    until: datetime | None = None,
    last_n: int = Query(default=200, ge=1, le=5000),
    level: list[str] | None = Query(default=None, description="Keep only these levels (INFO, WARNING, ERROR...)"),
):
    """Most recent log entries, optionally matching ``query`` (BM25 ranking or regex)."""
    from lazy_bird.log_search import LogSearchError, search_logs as search

    try:
        entries = search(query or None, since=since or (None if query else datetime(1970, 1, 1)), until=until, last_n=None if level else last_n, mode=mode, log_file=_log_file())
    except LogSearchError as error:
        raise InvalidInputError(str(error), code="invalid_log_query") from error
    if level:
        wanted = {value.upper() for value in level}
        entries = [entry for entry in entries if (entry.level or "").upper() in wanted][-last_n:]
    return [_entry(entry) for entry in entries]


@router.get("/trace")
def trace_calls(function: str, module: str | None = None, last_n: int = Query(default=5, ge=1, le=50)) -> list[dict[str, Any]]:
    """Call trees of a traced function (requires tracing or the @traced decorator)."""
    from lazy_bird.log_tree import node_to_dict, trace_call_trees

    return [node_to_dict(node) for node in trace_call_trees(function, module, last_n=last_n, log_file=_log_file())]


@router.get("/tracing", response_model=TracingIn)
def get_tracing():
    """Whether every lazy_bird call is traced in the logs (verbose, slows the server down)."""
    return TracingIn(enabled=logging_config.tracing_enabled())


@router.put("/tracing", response_model=TracingIn)
def set_tracing(payload: TracingIn):
    logging_config.set_package_tracing(payload.enabled)
    return TracingIn(enabled=logging_config.tracing_enabled())
