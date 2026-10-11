from __future__ import annotations

import io
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator


ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
HEADER_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\s*\|\s*"
    r"(?P<level>[^|]+?)\s*\|\s*(?P<process>[^|]*?)\s*\|\s*(?P<thread>[^|]*?)\s*\|\s*"
    r"(?P<location>[^|]*?)\s*\|\s?(?P<message>.*)$"
)


@dataclass(slots=True)
class LogEntry:
    start_line: int
    end_line: int
    timestamp: datetime | None
    level: str
    process: str
    thread: str
    location: str
    message: str
    payload: dict[str, object] | None
    raw_text: str
    score: float | None = None


class LogParseError(Exception):
    """Raised only for errors that prevent opening a log file."""


def _parse_header(line: str) -> tuple[datetime, str, str, str, str, str] | None:
    match = HEADER_RE.match(ANSI_RE.sub("", line.rstrip("\r\n")))
    if match is None:
        return None
    try:
        timestamp = datetime.fromisoformat(match.group("timestamp"))  # "2026-10-01 21:53:00.123"; strptime was half the reading time
    except ValueError:
        return None
    return (
        timestamp,
        match.group("level").strip(),
        match.group("process").strip(),
        match.group("thread").strip(),
        match.group("location").strip(),
        match.group("message"),
    )


def _entry_from_lines(start_line: int, lines: list[str]) -> LogEntry:
    first = _parse_header(lines[0])
    if first is None:
        clean = ANSI_RE.sub("", "".join(lines))
        return LogEntry(start_line, start_line + len(lines) - 1, None, "UNKNOWN", "", "", "", clean, None, "".join(lines))

    timestamp, level, process, thread, location, first_message = first
    continuation = [ANSI_RE.sub("", line.rstrip("\r\n")) for line in lines[1:]]
    message = "\n".join([first_message, *continuation])
    payload: dict[str, object] | None = None
    try:
        parsed = json.loads(ANSI_RE.sub("", first_message).strip())
        if isinstance(parsed, dict):
            payload = parsed
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return LogEntry(
        start_line=start_line,
        end_line=start_line + len(lines) - 1,
        timestamp=timestamp,
        level=level,
        process=process,
        thread=thread,
        location=location,
        message=message,
        payload=payload,
        raw_text="".join(lines),
    )


def _snapshot(log_file: Path) -> str:
    """The file as it is now, read at once and closed.

    The server keeps appending to its log while it is read (with call tracing, reading
    a line can write more than one): reading to the end of the file would never end. And
    on Windows an open file cannot be renamed, so the logger could not rotate it.
    """
    try:
        with log_file.open("rb") as handle:
            data = handle.read(os.fstat(handle.fileno()).st_size)
    except OSError as exc:
        raise LogParseError(f"Impossible de lire le fichier de logs: {log_file}: {exc}") from exc
    return data.decode("utf-8", errors="replace")


def iter_log_entries(log_file: Path) -> Iterator[LogEntry]:
    """Yield the log entries the file holds when the iteration starts."""
    current: list[str] = []
    start_line = 1
    lines = io.StringIO(_snapshot(log_file), newline=None)  # newline=None: Windows line ends become plain newlines
    for line_number, line in enumerate(lines, start=1):
        if _parse_header(line) is not None and current:
            yield _entry_from_lines(start_line, current)
            current = []
            start_line = line_number
        current.append(line)
    if current:
        yield _entry_from_lines(start_line, current)


def parse_log_file(log_file: Path) -> list[LogEntry]:
    """Parse a log file, retaining line ranges and continuation text."""
    return list(iter_log_entries(log_file))
