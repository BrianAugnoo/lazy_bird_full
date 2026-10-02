from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import re
from typing import Iterable

from lazy_bird.log_parser import LogEntry, iter_log_entries
from lazy_bird.log_render import entry_to_dict


@dataclass(slots=True)
class CallNode:
    call: LogEntry
    return_entry: LogEntry | None = None
    children: list["CallNode"] = field(default_factory=list)
    parent_missing: bool = False

    @property
    def payload(self) -> dict[str, object]:
        return self.call.payload or {}


def _event_entries(log_file: Path) -> list[LogEntry]:
    return [entry for entry in iter_log_entries(log_file) if entry.payload and entry.payload.get("event") in {"function_call", "function_return"}]


def _in_range(entry: LogEntry, since: datetime | None, until: datetime | None) -> bool:
    if entry.timestamp is None:
        return False
    timestamp = entry.timestamp
    if since is not None and timestamp < since.replace(tzinfo=None):
        return False
    if until is not None and timestamp > until.replace(tzinfo=None):
        return False
    return True


def trace_call_trees(
    function_name: str,
    module_name: str | None = None,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    last_n: int | None = None,
    log_file: Path = Path("logs.txt"),
) -> list[CallNode]:
    """Build complete descendant trees for matching function calls."""
    entries = [entry for entry in _event_entries(log_file) if _in_range(entry, since, until)]
    calls = [entry for entry in entries if entry.payload and entry.payload.get("event") == "function_call"]
    returns = {
        str(entry.payload.get("call_id")): entry
        for entry in entries
        if entry.payload and entry.payload.get("event") == "function_return" and entry.payload.get("call_id")
    }
    matching = [
        entry
        for entry in calls
        if entry.payload
        and entry.payload.get("function") == function_name
        and (module_name is None or entry.payload.get("module") == module_name)
    ]
    matching.sort(key=lambda entry: entry.start_line)
    if last_n is not None:
        matching = matching[-last_n:] if last_n else []

    nodes_by_id = {
        str(entry.payload.get("call_id")): CallNode(entry, returns.get(str(entry.payload.get("call_id"))))
        for entry in calls
        if entry.payload and entry.payload.get("call_id")
    }
    children_by_parent: dict[str, list[CallNode]] = {}
    for call_id, node in nodes_by_id.items():
        parent_id = node.payload.get("parent_id")
        if parent_id:
            children_by_parent.setdefault(str(parent_id), []).append(node)
    for parent_id, children in children_by_parent.items():
        if parent_id in nodes_by_id:
            nodes_by_id[parent_id].children.extend(sorted(children, key=lambda item: item.call.start_line))
        else:
            for child in children:
                child.parent_missing = True

    result: list[CallNode] = []
    for entry in matching:
        call_id = str(entry.payload.get("call_id"))
        result.append(nodes_by_id[call_id])
    return result


def _args_text(payload: dict[str, object]) -> str:
    args = payload.get("args")
    if not isinstance(args, dict) or not args:
        return ""
    if set(args) == {"positional", "keyword"}:
        positional = str(args.get("positional", "()"))
        keyword = str(args.get("keyword", "{}"))
        return f"{positional}, {keyword}" if keyword != "{}" else positional
    return ", ".join(f"{name}: {value}" for name, value in args.items())


def _error_text(entry: LogEntry) -> str:
    continuation = [line.strip() for line in entry.message.splitlines()[1:] if line.strip()]
    if continuation:
        return continuation[-1]
    return "Erreur sans détail"


def _result_text(node: CallNode) -> tuple[str, list[str]]:
    if node.return_entry is None or node.return_entry.payload is None:
        return "⚠ INTERROMPU (aucun retour ni erreur loggé)", []
    payload = node.return_entry.payload
    if payload.get("status") == "error":
        return f"✗ {_error_text(node.return_entry)}", node.return_entry.message.splitlines()[1:]
    return f"{payload.get('result', 'None')}", []


def render_call_tree(nodes: Iterable[CallNode], *, color: bool = False) -> str:
    """Render call trees as an indented human-readable string."""
    lines: list[str] = []

    def visit(node: CallNode, depth: int) -> None:
        payload = node.payload
        prefix = "    " * depth
        location = f"{payload.get('module', '<unknown>')}.{payload.get('function', '<unknown>')}"
        args = _args_text(payload)
        result, traceback_lines = _result_text(node)
        marker = " (parent introuvable)" if node.parent_missing else ""
        duration = ""
        if node.return_entry and node.return_entry.payload:
            duration = f" [{node.return_entry.payload.get('duration_ms', 0)} ms]"
        if color:
            from lazy_bird.log_render import _paint

            location = f"\x1b[2m{payload.get('module', '<unknown>')}\x1b[0m.\x1b[1;36m{payload.get('function', '<unknown>')}\x1b[0m"
            result = _paint(result, "red" if result.startswith("✗") else "yellow" if result.startswith("⚠") else "green", True)
            duration = f"\x1b[2m{duration}\x1b[0m"
        lines.append(f"{prefix}{location}({args}){marker}: -> {result}{duration}")
        for trace_line in traceback_lines:
            if trace_line.strip():
                lines.append(f"{prefix}    {_paint(trace_line, 'red', color)}")
        for child in node.children:
            visit(child, depth + 1)

    for node in nodes:
        visit(node, 0)
    return "\n".join(lines)


def render_raw_tree(nodes: Iterable[CallNode], *, color: bool = True) -> str:
    """Render raw source lines for all events in the selected subtrees."""
    selected: dict[tuple[int, int], LogEntry] = {}

    def collect(node: CallNode) -> None:
        selected[(node.call.start_line, node.call.end_line)] = node.call
        if node.return_entry:
            selected[(node.return_entry.start_line, node.return_entry.end_line)] = node.return_entry
        for child in node.children:
            collect(child)

    for node in nodes:
        collect(node)
    lines: list[str] = []
    for entry in sorted(selected.values(), key=lambda item: item.start_line):
        for offset, raw_line in enumerate(entry.raw_text.splitlines(), start=entry.start_line):
            raw_line = raw_line if color else re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", raw_line)
            lines.append(f"{offset}: {raw_line}")
    return "\n".join(lines)


def trace_function_calls(
    function_name: str,
    module_name: str | None = None,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    last_n: int | None = None,
    raw: bool = False,
    log_file: Path = Path("logs.txt"),
) -> str:
    """Find calls and render their complete descendant trees."""
    nodes = trace_call_trees(function_name, module_name, since=since, until=until, last_n=last_n, log_file=log_file)
    if not nodes:
        module_hint = f" dans {module_name}" if module_name else ""
        return f"Aucune correspondance pour {function_name}{module_hint}."
    return render_raw_tree(nodes) if raw else render_call_tree(nodes)


def node_to_dict(node: CallNode) -> dict[str, object]:
    """Serialize a call node for stable machine-readable CLI output."""
    return {
        "call": entry_to_dict(node.call),
        "return": entry_to_dict(node.return_entry) if node.return_entry else None,
        "parent_missing": node.parent_missing,
        "children": [node_to_dict(child) for child in node.children],
    }