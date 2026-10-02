from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import asdict
from typing import Iterable

from lazy_bird.log_parser import LogEntry


COLORS = {"reset": "\x1b[0m", "red": "\x1b[31m", "yellow": "\x1b[33m", "green": "\x1b[32m", "gray": "\x1b[90m"}


def color_enabled(mode: str, *, json_output: bool = False) -> bool:
    if json_output or mode == "never" or os.getenv("NO_COLOR") is not None:
        return False
    return mode == "always" or (mode == "auto" and sys.stdout.isatty())


def _paint(text: str, color: str, enabled: bool) -> str:
    return f"{COLORS[color]}{text}{COLORS['reset']}" if enabled else text


def entry_to_dict(entry: LogEntry) -> dict[str, object]:
    result = asdict(entry)
    result["timestamp"] = entry.timestamp.isoformat() if entry.timestamp else None
    return result


def render_search_results(entries: Iterable[LogEntry], *, query: str | None = None, color: bool = False) -> str:
    lines: list[str] = []
    pattern = re.compile(re.escape(query), re.IGNORECASE) if query else None
    for entry in entries:
        text = entry.raw_text.rstrip("\r\n")
        if not color:
            text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
        if pattern:
            text = pattern.sub(lambda match: _paint(match.group(0), "yellow", color), text)
        lines.append(f"{_paint(f'{entry.start_line}-{entry.end_line}', 'gray', color)} {text}")
    return "\n".join(lines)


def json_output(command: str, results: object, *, error: str | None = None) -> str:
    body: dict[str, object] = {"command": command, "ok": error is None}
    if error is not None:
        body["error"] = error
    else:
        body["results"] = results
    return json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True)