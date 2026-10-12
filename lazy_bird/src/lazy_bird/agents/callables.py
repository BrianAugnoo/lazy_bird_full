"""Discovery shared by tools and hooks.

A module lives in ``{root}/{extension_name}/{module}.py`` and lists its entries in a
variable (``tools`` or ``hooks``). Each entry is either:

- a function, called as is;
- a class, whose public methods (names not starting with ``_``) are the entries.
  The class is instantiated when one of its methods is first needed, with:

  - the *context*: values the caller gives every entry (hooks: ``conversation_id``).
    A class must take each of them in ``__init__``; a function takes them as arguments;
  - ``settings``: the module's settings model (``ToolSettings`` / ``HookSettings``),
    filled with the kwargs saved in the database, if ``__init__`` takes ``settings``;
  - the key/value pairs of the session ``meta``: all of them if ``__init__`` accepts
    ``**kwargs``, otherwise those matching its parameter names.

Ids are ``{extension}-{module}-{function}`` or ``{extension}-{module}-{Class}-{method}``.
Python identifiers cannot contain ``-``, so ids are unambiguous, and they are valid
LLM function names (``^[a-zA-Z0-9_-]{1,64}$``).
"""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any, Callable, Iterable

from pydantic import BaseModel

from lazy_bird.errors import AppError, InvalidSettingsError
from lazy_bird.extension import ExtensionContractError
from lazy_bird.extension.discovery import LoadFailure, import_module, iter_extension_modules
from lazy_bird.extension.settings import SettingsContract, settings_contract

ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
SETTINGS_PARAMETER = "settings"

Describe = Callable[[Callable[..., Any], str, "type | None"], tuple[str, dict[str, Any]]]


class NotConfiguredError(AppError):
    """A class entry needs settings that are missing or invalid."""

    status_code = 422
    code = "not_configured"


class MissingMetaError(AppError):
    """A class entry needs session meta values the session does not define."""

    status_code = 422
    code = "missing_session_meta"


@dataclass(frozen=True)
class Entry:
    """One tool or hook: a function, or a public method of a class."""

    id: str
    name: str
    extension: str
    module: str
    file_path: str
    function: Callable[..., Any]
    owner: type | None = None
    needs_settings: bool = False
    meta_params: tuple[str, ...] = ()
    required_meta: tuple[str, ...] = ()
    accepts_any_meta: bool = False
    description: str = ""
    schema: dict[str, Any] = field(default_factory=dict)

    @property
    def is_method(self) -> bool:
        return self.owner is not None

    @property
    def instance_key(self) -> str:
        return f"{self.file_path}:{self.owner.__qualname__}" if self.owner else self.id


def without_self(function: Callable[..., Any]) -> Callable[..., Any]:
    """A signature-only stand-in for a method, without its ``self`` parameter."""
    signature = inspect.signature(function)
    parameters = list(signature.parameters.values())[1:]

    def stand_in(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("signature-only stand-in")

    stand_in.__name__ = function.__name__
    stand_in.__qualname__ = function.__qualname__
    stand_in.__doc__ = function.__doc__
    stand_in.__signature__ = signature.replace(parameters=parameters)
    stand_in.__annotations__ = {name: value for name, value in getattr(function, "__annotations__", {}).items() if name in {p.name for p in parameters} or name == "return"}
    return stand_in


def _constructor(owner: type, context: tuple[str, ...]) -> tuple[bool, tuple[str, ...], tuple[str, ...], bool]:
    """Return (needs settings, meta parameters, required meta parameters, accepts **kwargs)."""
    parameters = list(inspect.signature(owner.__init__).parameters.values())[1:]
    named = [parameter for parameter in parameters if parameter.kind in (parameter.POSITIONAL_OR_KEYWORD, parameter.KEYWORD_ONLY)]
    missing = [name for name in context if name not in {parameter.name for parameter in named}]
    if missing:
        raise ExtensionContractError(f"{owner.__name__}.__init__ must take {', '.join(repr(name) for name in missing)}")
    needs_settings = any(parameter.name == SETTINGS_PARAMETER for parameter in named)
    meta = [parameter for parameter in named if parameter.name != SETTINGS_PARAMETER and parameter.name not in context]
    required = tuple(parameter.name for parameter in meta if parameter.default is parameter.empty)
    accepts_any = any(parameter.kind == parameter.VAR_KEYWORD for parameter in parameters)
    if any(parameter.kind == parameter.VAR_POSITIONAL for parameter in parameters):
        raise ExtensionContractError(f"{owner.__name__}.__init__ cannot take *args")
    return needs_settings, tuple(parameter.name for parameter in meta), required, accepts_any


def _public_methods(owner: type) -> list[Callable[..., Any]]:
    methods = []
    for name, value in owner.__dict__.items():
        if name.startswith("_"):
            continue
        if isinstance(value, (staticmethod, classmethod)):
            raise ExtensionContractError(f"{owner.__name__}.{name}: static and class methods are not supported")
        if inspect.isfunction(value):
            methods.append(value)
    if not methods:
        raise ExtensionContractError(f"{owner.__name__} has no public method")
    return methods


def build_entries(
    item: Any,
    *,
    extension: str,
    module: str,
    file_path: str,
    describe: Describe,
    context: tuple[str, ...] = (),
) -> list[Entry]:
    """Turn one item of a ``tools``/``hooks`` list into entries.

    ``describe(signature_function, name, owner)`` validates the callable and returns
    its description and schema; for methods it receives a stand-in without ``self``
    and the class as ``owner`` (``None`` for functions).
    """
    if inspect.isclass(item):
        needs_settings, meta, required, any_meta = _constructor(item, context)
        entries = []
        for method in _public_methods(item):
            description, schema = describe(without_self(method), method.__name__, item)
            entries.append(
                Entry(
                    id=_entry_id(extension, module, item.__name__, method.__name__),
                    name=method.__name__,
                    extension=extension,
                    module=module,
                    file_path=file_path,
                    function=method,
                    owner=item,
                    needs_settings=needs_settings,
                    meta_params=meta,
                    required_meta=required,
                    accepts_any_meta=any_meta,
                    description=description,
                    schema=schema,
                )
            )
        return entries
    if inspect.isfunction(item):
        description, schema = describe(item, item.__name__, None)
        return [
            Entry(
                id=_entry_id(extension, module, item.__name__),
                name=item.__name__,
                extension=extension,
                module=module,
                file_path=file_path,
                function=item,
                description=description,
                schema=schema,
            )
        ]
    raise ExtensionContractError(f"{item!r} is neither a function nor a class")


def _entry_id(*parts: str) -> str:
    entry_id = "-".join(parts)
    if not ID_PATTERN.match(entry_id):
        raise ExtensionContractError(f"id '{entry_id}' must match {ID_PATTERN.pattern} (shorten the extension, module or function name)")
    return entry_id


@dataclass
class Discovery:
    entries: dict[str, Entry] = field(default_factory=dict)
    settings: dict[str, SettingsContract] = field(default_factory=dict)
    failures: list[LoadFailure] = field(default_factory=list)


def discover(
    package: str,
    *,
    kind: str,
    variable: str,
    settings_attribute: str,
    describe: Describe,
    context: tuple[str, ...] = (),
) -> Discovery:
    """Load every ``{extension}/{module}.py`` of ``package`` and collect its entries.

    ``context``: names of the values the caller gives every entry (see the module docstring).
    """
    found = Discovery()
    for extension, module_name, import_path in iter_extension_modules(package):
        file_path = f"{extension}/{module_name}.py"
        try:
            module = import_module(import_path)
            entries, contract = _module_entries(module, extension, module_name, file_path, variable, settings_attribute, describe, context)
        except Exception as error:
            found.failures.append(LoadFailure(kind, file_path, str(error)))
            continue
        duplicate = next((entry.id for entry in entries if entry.id in found.entries), None)
        if duplicate:
            found.failures.append(LoadFailure(kind, file_path, f"duplicate id '{duplicate}'"))
            continue
        found.entries.update({entry.id: entry for entry in entries})
        if contract is not None:
            found.settings[file_path] = contract
    return found


def _module_entries(module: ModuleType, extension, module_name, file_path, variable, settings_attribute, describe, context):
    items = getattr(module, variable, None)
    if not isinstance(items, (list, tuple)):
        raise ExtensionContractError(f"missing '{variable}' list")
    contract = settings_contract(module, settings_attribute)
    entries = [
        entry
        for item in items
        for entry in build_entries(item, extension=extension, module=module_name, file_path=file_path, describe=describe, context=context)
    ]
    if any(entry.needs_settings for entry in entries) and contract is None:
        raise ExtensionContractError(f"a class takes 'settings' but the module defines no {settings_attribute}")
    return entries, contract


class Runner:
    """Calls entries during one agent run, creating each class instance once.

    ``context``: the values given to every class constructor (see the module docstring).
    """

    def __init__(self, meta: dict[str, Any] | None, settings_for: Callable[[str], BaseModel], context: dict[str, Any] | None = None) -> None:
        self.meta = dict(meta or {})
        self.settings_for = settings_for
        self.context = dict(context or {})
        self._instances: dict[str, Any] = {}

    def instance(self, entry: Entry) -> Any:
        if entry.instance_key not in self._instances:
            kwargs: dict[str, Any] = dict(self.context)
            if entry.needs_settings:
                kwargs[SETTINGS_PARAMETER] = self.settings_for(entry.file_path)
            missing = [name for name in entry.required_meta if name not in self.meta]
            if missing:
                raise MissingMetaError(
                    f"'{entry.id}' needs the session meta value(s): {', '.join(missing)}.",
                    details={"missing": missing},
                )
            if entry.accepts_any_meta:
                kwargs.update({name: value for name, value in self.meta.items() if name != SETTINGS_PARAMETER and name not in self.context})
            else:
                kwargs.update({name: self.meta[name] for name in entry.meta_params if name in self.meta})
            self._instances[entry.instance_key] = entry.owner(**kwargs)
        return self._instances[entry.instance_key]

    def call(self, entry: Entry, arguments: dict[str, Any] | None = None) -> Any:
        if entry.is_method:
            return getattr(self.instance(entry), entry.name)(**(arguments or {}))
        return entry.function(**(arguments or {}))


def settings_loader(contracts: dict[str, SettingsContract], saved: Callable[[str], dict[str, Any]], kind: str) -> Callable[[str], BaseModel]:
    """Build the function giving the validated settings of a module."""

    def load(file_path: str) -> BaseModel:
        contract = contracts.get(file_path)
        if contract is None:
            raise NotConfiguredError(f"{kind} module '{file_path}' has no settings model.")
        try:
            return contract.validate(saved(file_path))
        except InvalidSettingsError as error:
            raise NotConfiguredError(
                f"{kind} module '{file_path}' is not configured: {', '.join(error.fields)}.",
                details={"file_path": file_path, "fields": error.fields},
            ) from error

    return load


def unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))
