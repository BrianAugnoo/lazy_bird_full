"""Hooks: called on every agent turn, before the conversation is sent to the LLM.

Contract of a hooks module (``agents/hook/{extension_name}/{module}.py``):

- ``hooks``: list of functions and/or classes (see ``agents/callables.py``). A hook
  (function or public method) takes exactly one argument, ``conversation_id``, and
  changes the conversation through lazy_bird's CRUD (inject context, compress old
  messages, check safety...). Raising stops the turn and records an error message;
- ``HookSettings`` (optional, for class hooks): pydantic model of the module's
  configuration, with optional ``fields``; saved in the ``hooksettings`` table.

Hook ids follow the tool scheme: ``{extension}-{module}-{function}``.
"""

from __future__ import annotations

import inspect
from typing import Any

from lazy_bird.agents.callables import Discovery, Entry, Runner, discover, settings_loader
from lazy_bird.crud.extension_settings import ModuleSettingsStore
from lazy_bird.errors import NotFoundError
from lazy_bird.extension import ExtensionContractError
from lazy_bird.extension.discovery import record_failures
from lazy_bird.models.extension_settings import HookSettings as HookSettingsTable

HOOK_PARAMETER = "conversation_id"
settings_store = ModuleSettingsStore(HookSettingsTable, "hook")
_found = Discovery()


def _describe(function, name: str) -> tuple[str, dict[str, Any]]:
    parameters = list(inspect.signature(function).parameters)
    if parameters != [HOOK_PARAMETER]:
        raise ExtensionContractError(f"hook '{name}' must take exactly one argument named '{HOOK_PARAMETER}' (got {parameters})")
    return (inspect.getdoc(function) or "").split("\n\n")[0], {}


def initialize_hooks() -> Discovery:
    global _found
    _found = discover("lazy_bird.agents.hook", kind="hook", variable="hooks", settings_attribute="HookSettings", describe=_describe)
    record_failures("hook", _found.failures)
    settings_store.sync(_found.settings)
    return _found


def all_hooks() -> list[Entry]:
    return list(_found.entries.values())


def get(hook_id: str) -> Entry:
    entry = _found.entries.get(hook_id)
    if entry is None:
        raise NotFoundError("Hook", hook_id)
    return entry


def runner(meta: dict[str, Any] | None) -> Runner:
    return Runner(meta, settings_loader(_found.settings, settings_store.saved, "Hook"))


def run_hooks(hook_ids: list[str], conversation_id: int, meta: dict[str, Any] | None) -> None:
    """Call an agent's hooks in order with ``conversation_id``."""
    calls = runner(meta)
    for hook_id in hook_ids:
        calls.call(get(hook_id), {HOOK_PARAMETER: conversation_id})
