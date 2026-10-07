"""The ``*Settings`` + ``fields`` + ``kwargs_key`` contract.

A configurable extension module (embedding/inference engine, class tool, hook)
declares a pydantic model describing its configuration, under a name fixed by its
discovery point (``EngineSettings``, ``ToolSettings`` or ``HookSettings``)::

    class EngineSettings(BaseModel):
        model_id: int
        device: str | None = None

It may also declare ``fields`` to replace the default form widget of some attributes::

    fields = {
        "model_id": {
            "default_field": True,                 # True: frontend TS function, False: custom HTML
            "content": "default.basic.reference",  # "{extension_name}.{file_name}.{function}" or an HTML string
            "args": {"endpoint": "/models/"},      # arguments of the TS function; empty for custom HTML
        },
    }

From these two declarations this module derives, without any hand-written code:

- ``kwargs_key``: one descriptor per attribute, stored in the database and sent to
  the frontend to build the form. Standard attributes get a default widget from
  ``web/src/modules/fields/default/basic.ts``; ``fields`` entries override the
  widget part (``default_field``, ``content``, ``args``) of their attribute;
- validation: ``SettingsContract.validate(kwargs)`` returns the parsed model or
  raises ``InvalidSettingsError`` with one message per attribute.
"""

from __future__ import annotations

import re
import types
from enum import Enum
from pathlib import PurePath
from typing import Annotated, Any, Literal, Mapping, Union, get_args, get_origin

import annotated_types
from pydantic import BaseModel, ConfigDict, Field, SecretBytes, SecretStr, ValidationError, model_validator
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined, to_jsonable_python

from lazy_bird.errors import InvalidSettingsError
from lazy_bird.extension import ExtensionContractError

FIELD_FUNCTION_PATTERN = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z_$][A-Za-z0-9_$]*$")
ROOT_ERROR_KEY = "__root__"


class FieldSpec(BaseModel):
    """Widget of one settings attribute: a frontend function or a custom HTML snippet."""

    default_field: bool
    content: str = Field(min_length=1)
    args: dict[str, Any] = Field(default_factory=dict)
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _check_content(self) -> "FieldSpec":
        if self.default_field and not FIELD_FUNCTION_PATTERN.match(self.content):
            raise ValueError("content must be '{extension_name}.{file_name}.{function}' when default_field is true")
        if not self.default_field and self.args:
            raise ValueError("args must be empty for a custom HTML field")
        return self


def _unwrap(annotation: Any) -> tuple[Any, bool]:
    """Strip ``Annotated`` and ``Optional`` wrappers; return the inner type and nullability."""
    nullable = False
    while True:
        origin = get_origin(annotation)
        if origin is Annotated:
            annotation = get_args(annotation)[0]
        elif origin in (Union, types.UnionType):
            members = [member for member in get_args(annotation) if member is not type(None)]
            nullable = nullable or len(members) != len(get_args(annotation))
            if len(members) != 1:
                return annotation, nullable
            annotation = members[0]
        else:
            return annotation, nullable


def _value_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return "string"


def _widget(annotation: Any) -> tuple[str, str, dict[str, Any]]:
    """Return ``(value type, default widget function, widget args)`` for an annotation."""
    annotation, _ = _unwrap(annotation)
    origin = get_origin(annotation)
    if origin is Literal:
        options = list(get_args(annotation))
        return (_value_type(options[0]) if options else "string"), "select", {"options": options}
    if isinstance(annotation, type):
        if issubclass(annotation, Enum):
            options = [member.value for member in annotation]
            return (_value_type(options[0]) if options else "string"), "select", {"options": options}
        if issubclass(annotation, bool):
            return "boolean", "checkbox", {}
        if issubclass(annotation, int):
            return "integer", "integer", {}
        if issubclass(annotation, float):
            return "number", "number", {}
        if issubclass(annotation, (SecretStr, SecretBytes)):
            return "string", "password", {}
        if issubclass(annotation, (str, PurePath)):
            return "string", "text", {}
        if issubclass(annotation, (dict, BaseModel)):
            return "object", "json", {}
    if origin in (list, tuple, set, frozenset):
        items = [_unwrap(item)[0] for item in get_args(annotation) if item is not Ellipsis]
        if items and all(item is str for item in items):
            return "array", "list", {}
        return "array", "json", {}
    if origin is dict:
        return "object", "json", {}
    return "any", "json", {}


def _constraints(field: FieldInfo) -> dict[str, Any]:
    constraints: dict[str, Any] = {}
    for item in field.metadata:
        if isinstance(item, annotated_types.Ge):
            constraints["min"] = item.ge
        elif isinstance(item, annotated_types.Gt):
            constraints["min"] = item.gt
        elif isinstance(item, annotated_types.Le):
            constraints["max"] = item.le
        elif isinstance(item, annotated_types.Lt):
            constraints["max"] = item.lt
        elif isinstance(item, annotated_types.MinLen):
            constraints["min_length"] = item.min_length
        elif isinstance(item, annotated_types.MaxLen):
            constraints["max_length"] = item.max_length
    return constraints


def _jsonable(value: Any) -> Any:
    if isinstance(value, (SecretStr, SecretBytes)):
        return value.get_secret_value()
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    try:
        return to_jsonable_python(value)
    except Exception:
        return str(value)


def _default(field: FieldInfo) -> Any:
    if field.is_required():
        return None
    if field.default is not PydanticUndefined:
        return _jsonable(field.default)
    try:
        return _jsonable(field.get_default(call_default_factory=True))
    except Exception:
        return None


def describe_field(name: str, field: FieldInfo) -> dict[str, Any]:
    """Build the default ``kwargs_key`` descriptor of one settings attribute."""
    value_type, widget, args = _widget(field.annotation)
    _, nullable = _unwrap(field.annotation)
    return {
        "default_field": True,
        "content": f"default.basic.{widget}",
        "args": {**args, **_constraints(field)},
        "type": value_type,
        "required": field.is_required(),
        "nullable": nullable,
        "default": _default(field),
        "title": field.title or name.replace("_", " ").capitalize(),
        "description": field.description,
    }


def validation_messages(error: ValidationError) -> dict[str, str]:
    """Flatten a pydantic error into ``{attribute path: message}``."""
    messages: dict[str, str] = {}
    for item in error.errors():
        key = ".".join(str(part) for part in item.get("loc", ())) or ROOT_ERROR_KEY
        message = item.get("msg", "Invalid value")
        messages[key] = f"{messages[key]}; {message}" if key in messages else message
    return messages


class SettingsContract:
    """Settings model of an extension, with its optional ``fields`` overrides."""

    def __init__(self, model: type[BaseModel], fields: Mapping[str, Any] | None = None) -> None:
        if not (isinstance(model, type) and issubclass(model, BaseModel)):
            raise ExtensionContractError(f"{model!r} is not a pydantic BaseModel subclass")
        if fields is not None and not isinstance(fields, Mapping):
            raise ExtensionContractError("'fields' must be a dict {attribute: field spec}")
        self.model = model
        self.fields: dict[str, FieldSpec] = {}
        for name, spec in (fields or {}).items():
            if name not in model.model_fields:
                raise ExtensionContractError(f"'fields' declares '{name}', which is not an attribute of {model.__name__}")
            try:
                self.fields[name] = FieldSpec.model_validate(spec)
            except ValidationError as error:
                raise ExtensionContractError(f"Invalid field spec for '{name}': {validation_messages(error)}") from error

    def has(self, attribute: str) -> bool:
        return attribute in self.model.model_fields

    def kwargs_key(self) -> dict[str, dict[str, Any]]:
        """Describe every attribute for the frontend, applying ``fields`` overrides."""
        descriptors = {}
        for name, field in self.model.model_fields.items():
            descriptor = describe_field(name, field)
            if name in self.fields:
                descriptor.update(self.fields[name].model_dump())
            descriptors[name] = descriptor
        return descriptors

    def errors(self, kwargs: Mapping[str, Any] | None) -> dict[str, str]:
        """Return ``{attribute: message}`` for invalid kwargs, or an empty dict."""
        try:
            self.validate(kwargs)
        except InvalidSettingsError as error:
            return error.fields
        return {}

    def validate(self, kwargs: Mapping[str, Any] | None) -> BaseModel:
        """Parse kwargs into the settings model; raise ``InvalidSettingsError`` on failure."""
        if kwargs is not None and not isinstance(kwargs, Mapping):
            raise InvalidSettingsError({ROOT_ERROR_KEY: "Settings must be an object"})
        values = dict(kwargs or {})
        unknown = {name: "Unknown setting" for name in values if name not in self.model.model_fields}
        try:
            settings = self.model.model_validate(values)
        except ValidationError as error:
            raise InvalidSettingsError({**validation_messages(error), **unknown}) from error
        if unknown:
            raise InvalidSettingsError(unknown)
        return settings

    def dump(self, settings: BaseModel) -> dict[str, Any]:
        """Serialize the explicitly provided attributes of parsed settings for storage."""
        return {name: _jsonable(getattr(settings, name)) for name in settings.model_fields_set}

    def normalize(self, kwargs: Mapping[str, Any] | None) -> dict[str, Any]:
        """Validate kwargs and return their normalized storable form."""
        return self.dump(self.validate(kwargs))


def settings_contract(module: Any, attribute: str, *, required: bool = False) -> SettingsContract | None:
    """Return the contract declared by ``module.<attribute>`` (+ ``module.fields``).

    Returns ``None`` when the module declares no settings model and ``required`` is
    false. Raises ``ExtensionContractError`` when the declaration is malformed.
    """
    model = getattr(module, attribute, None)
    if model is None:
        if required:
            raise ExtensionContractError(f"missing '{attribute}'")
        if getattr(module, "fields", None):
            raise ExtensionContractError(f"'fields' is declared without '{attribute}'")
        return None
    return SettingsContract(model, getattr(module, "fields", None))
