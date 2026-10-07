"""Tools agents can call.

Contract of a tools module (``agents/tools/{extension_name}/{module}.py``):

- ``tools``: list of functions and/or classes (see ``agents/callables.py``). Every
  function or public method needs a docstring with an ``Args:`` section and type
  hints: they become the JSON schema shown to the LLM (``self`` is never shown);
- ``ToolSettings`` (optional, for class tools): pydantic model of the module's
  configuration, with optional ``fields`` widgets. Saved values live in the
  ``toolsettings`` table and are edited through ``/tools/settings``.

Tool ids are ``{extension}-{module}-{function}`` (``...-{Class}-{method}`` for
methods). An agent lists tool ids; the LLM sees plain names, except that when two
of an agent's tools share a name, the one from ``default/`` (else the first one)
keeps it and the others are shown under their id.
"""

from __future__ import annotations

from typing import Any

from transformers.utils import get_json_schema

from lazy_bird.agents.callables import Discovery, Entry, Runner, discover, settings_loader
from lazy_bird.crud.extension_settings import ModuleSettingsStore
from lazy_bird.errors import NotFoundError
from lazy_bird.extension.discovery import LoadFailure, record_failures
from lazy_bird.models.extension_settings import ToolSettings as ToolSettingsTable

DEFAULT_EXTENSION = "default"
settings_store = ModuleSettingsStore(ToolSettingsTable, "tool")
_found = Discovery()


def _describe(function, name: str) -> tuple[str, dict[str, Any]]:
    schema = get_json_schema(function)
    schema["function"].pop("return", None)
    return schema["function"].get("description", ""), schema


def initialize_tools() -> Discovery:
    """Discover every tool and register the settings forms of class tools."""
    global _found
    found = discover("lazy_bird.agents.tools", kind="tool", variable="tools", settings_attribute="ToolSettings", describe=_describe)
    seen: dict[str, Entry] = {}
    for entry in list(found.entries.values()):
        if entry.extension != DEFAULT_EXTENSION:
            continue
        if entry.name in seen:
            del found.entries[entry.id]
            found.failures.append(LoadFailure("tool", entry.file_path, f"default tool name '{entry.name}' is already used by {seen[entry.name].id}"))
        else:
            seen[entry.name] = entry
    _found = found
    record_failures("tool", found.failures)
    settings_store.sync(found.settings)
    return found


def all_tools() -> list[Entry]:
    return list(_found.entries.values())


def get(tool_id: str) -> Entry:
    entry = _found.entries.get(tool_id)
    if entry is None:
        raise NotFoundError("Tool", tool_id)
    return entry


def llm_names(tool_ids: list[str]) -> dict[str, str]:
    """Name shown to the LLM for each tool id of an agent (collisions get the id)."""
    entries = [get(tool_id) for tool_id in tool_ids]
    by_name: dict[str, list[Entry]] = {}
    for entry in entries:
        by_name.setdefault(entry.name, []).append(entry)
    names = {}
    for name, group in by_name.items():
        keeper = next((entry for entry in group if entry.extension == DEFAULT_EXTENSION), group[0])
        for entry in group:
            names[entry.id] = name if entry is keeper else entry.id
    return names


def llm_schema(entry: Entry, name: str) -> dict[str, Any]:
    """OpenAI-style tool definition of an entry under the name shown to the LLM."""
    return {"type": "function", "function": {**entry.schema["function"], "name": name}}


def runner(meta: dict[str, Any] | None) -> Runner:
    """Executes tool calls for one agent run (one instance per tool class)."""
    return Runner(meta, settings_loader(_found.settings, settings_store.saved, "Tool"))
