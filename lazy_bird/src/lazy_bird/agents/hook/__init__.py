"""Hooks: called on every agent turn, before the conversation is sent to the LLM.

Contract of a hooks module (``agents/hook/{extension_name}/{module}.py``):

- ``hooks``: list of functions and/or classes (see ``agents/callables.py``). A function
  takes exactly one argument, ``conversation_id``. A class takes ``conversation_id`` in
  ``__init__`` (besides ``settings`` and session meta values) and its public methods
  take no argument: it is built anew each time the agent's hooks run, and its methods
  share that instance. A hook changes the conversation through lazy_bird's CRUD
  (inject context, compress old messages, check safety...). Raising stops the turn and
  records an error message;
- ``HookSettings`` (optional, for class hooks): pydantic model of the module's
  configuration, with optional ``fields``; saved in the ``hooksettings`` table.

A hook's docstring is its description (shown on the Hooks page).

Message hooks: instead of changing a message's text, a hook can attach data to a system
or user message (``message_crud.edit_hooks``), under a key of its own by convention
(``hooks["system"]`` for ``default/system.py``). ``format_messages`` hands that data to
the LLM as YAML, after the system prompt and before the user's text; the stored content
never changes.

Hook ids follow the tool scheme: ``{extension}-{module}-{function}``.
"""

from __future__ import annotations

import inspect
from typing import Any

import yaml

from lazy_bird.agents.callables import Discovery, Entry, Runner, discover, settings_loader
from lazy_bird.crud import message as message_crud
from lazy_bird.crud.extension_settings import ModuleSettingsStore
from lazy_bird.errors import NotFoundError
from lazy_bird.extension import ExtensionContractError
from lazy_bird.extension.discovery import record_failures
from lazy_bird.models.extension_settings import HookSettings as HookSettingsTable
from lazy_bird.schemas.message import MessageOut

HOOK_PARAMETER = "conversation_id"
PACKAGE = "lazy_bird.agents.hook"
settings_store = ModuleSettingsStore(HookSettingsTable, "hook")
_found = Discovery()


def _describe(function, name: str, owner: type | None) -> tuple[str, dict[str, Any]]:
    parameters = list(inspect.signature(function).parameters)
    if owner is not None and parameters:
        raise ExtensionContractError(f"hook method '{owner.__name__}.{name}' must take no argument: '{HOOK_PARAMETER}' goes to {owner.__name__}.__init__ (got {parameters})")
    if owner is None and parameters != [HOOK_PARAMETER]:
        raise ExtensionContractError(f"hook '{name}' must take exactly one argument named '{HOOK_PARAMETER}' (got {parameters})")
    return inspect.getdoc(function) or "", {}


def discover_hooks(package: str = PACKAGE) -> Discovery:
    return discover(package, kind="hook", variable="hooks", settings_attribute="HookSettings", describe=_describe, context=(HOOK_PARAMETER,))


def initialize_hooks() -> Discovery:
    global _found
    _found = discover_hooks()
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


def runner(meta: dict[str, Any] | None, conversation_id: int) -> Runner:
    """Calls hooks for one pass over a conversation (classes are built with its id)."""
    return Runner(meta, settings_loader(_found.settings, settings_store.saved, "Hook"), {HOOK_PARAMETER: conversation_id})


def run_hooks(hook_ids: list[str], conversation_id: int, meta: dict[str, Any] | None) -> None:
    """Call an agent's hooks in order: functions with ``conversation_id``, methods without."""
    calls = runner(meta, conversation_id)
    for hook_id in hook_ids:
        entry = get(hook_id)
        calls.call(entry, None if entry.is_method else {HOOK_PARAMETER: conversation_id})


# ----------------------------------------------------------------- message hooks
class _Dumper(yaml.SafeDumper):
    """Writes multi-line strings as literal blocks, as they read best."""


_Dumper.add_representer(str, lambda dumper, text: dumper.represent_scalar("tag:yaml.org,2002:str", text, style="|" if "\n" in text else None))


def _without_none(value: Any) -> Any:
    """``value`` without the keys holding ``None``, at any depth; a mapping left empty goes too."""
    if isinstance(value, dict):
        kept = {key: _without_none(item) for key, item in value.items() if item is not None}
        return {key: item for key, item in kept.items() if item != {}}
    if isinstance(value, list):
        return [_without_none(item) for item in value]
    return value


def hooks_text(hooks: dict[str, Any] | None) -> str:
    """A message's hooks as the LLM reads them: YAML, or "" when nothing is left to say."""
    cleaned = _without_none(hooks or {})
    if not cleaned:
        return ""
    return yaml.dump(cleaned, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=float("inf")).rstrip("\n")


def format_messages(conversation_id: int) -> list[MessageOut]:
    """The conversation's messages as the LLM reads them (the stored ones are unchanged).

    The hooks of a system message are added at the end of its content, after a newline;
    those of a user message at the beginning. Other roles keep their content.
    """
    formatted = []
    for message in message_crud.for_conversation(conversation_id):
        text = hooks_text(message.hooks) if message.role in ("system", "user") else ""
        if text:
            parts = [message.content, text] if message.role == "system" else [text, message.content]
            message = message.model_copy(update={"content": "\n".join(part for part in parts if part)})
        formatted.append(message)
    return formatted
