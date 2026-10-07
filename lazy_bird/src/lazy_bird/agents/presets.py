"""JSON presets stored in ``{root}/{extension_name}/{name}.json`` (agent and session presets).

Guardrail: the file name must equal the ``name`` key, so two presets of one extension
can never share a name. Presets are identified by ``"{extension}/{name}"``. A preset
whose references are broken (unknown tool, missing sub-agent preset...) is still
listed, with ``valid: false`` and one message per key, so it can be fixed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from lazy_bird.agents.files import CUSTOM, check_name, ensure_layout, extensions, require_custom, split_id, write_text
from lazy_bird.errors import ConflictError, InvalidInputError, NotFoundError
from lazy_bird.extension.settings import validation_messages

Data = TypeVar("Data", bound=BaseModel)


@dataclass(frozen=True)
class Preset(Generic[Data]):
    id: str
    extension: str
    name: str
    data: Data | None
    errors: dict[str, str]

    @property
    def valid(self) -> bool:
        return not self.errors

    @property
    def editable(self) -> bool:
        return self.extension == CUSTOM


class PresetRegistry(Generic[Data]):
    def __init__(self, root: Path, schema: type[Data], kind: str, references: Callable[[Data], dict[str, str]]) -> None:
        self.root = root
        self.schema = schema
        self.kind = kind
        self.references = references

    def ensure_folders(self) -> None:
        ensure_layout(self.root)

    def _load(self, extension: str, path: Path) -> Preset[Data]:
        preset_id = f"{extension}/{path.stem}"
        try:
            data = self.schema.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except ValueError as error:
            messages = validation_messages(error) if isinstance(error, ValidationError) else {"__root__": f"Invalid JSON: {error}"}
            return Preset(preset_id, extension, path.stem, None, messages)
        errors = {}
        if data.name != path.stem:
            errors["name"] = f"must equal the file name '{path.stem}'"
        errors.update(self.references(data))
        return Preset(preset_id, extension, path.stem, data, errors)

    def presets(self) -> list[Preset[Data]]:
        return [self._load(folder.name, path) for folder in extensions(self.root) for path in sorted(folder.glob("*.json"))]

    def get(self, preset_id: str) -> Preset[Data]:
        extension, name = split_id(preset_id, f"{self.kind.capitalize()} preset")
        path = self.root / extension / f"{name}.json"
        if not path.is_file():
            raise NotFoundError(f"{self.kind.capitalize()} preset", preset_id, code="preset_not_found")
        return self._load(extension, path)

    def exists(self, preset_id: str) -> bool:
        try:
            self.get(preset_id)
        except NotFoundError:
            return False
        return True

    def valid_data(self, preset_id: str) -> Data:
        """The data of a preset, or an error listing what is wrong with it."""
        preset = self.get(preset_id)
        if not preset.valid:
            raise InvalidInputError(
                f"The {self.kind} preset '{preset_id}' is invalid.",
                code="invalid_preset",
                details={"preset": preset_id, "fields": preset.errors},
            )
        return preset.data

    def _write(self, data: Data, *, new: bool) -> Preset[Data]:
        path = self.root / CUSTOM / f"{check_name(data.name)}.json"
        if new and path.exists():
            raise ConflictError(f"The {self.kind} preset '{CUSTOM}/{data.name}' already exists.", code="preset_exists")
        errors = self.references(data)
        if errors:
            raise InvalidInputError(f"The {self.kind} preset has invalid references.", code="invalid_preset", details={"fields": errors})
        write_text(path, json.dumps(data.model_dump(), indent=2, ensure_ascii=False) + "\n")
        return self.get(f"{CUSTOM}/{data.name}")

    def create(self, data: Data) -> Preset[Data]:
        return self._write(data, new=True)

    def update(self, preset_id: str, data: Data) -> Preset[Data]:
        preset = self.get(preset_id)
        require_custom(preset.extension, f"{self.kind.capitalize()} presets")
        if data.name != preset.name:
            raise InvalidInputError("A preset cannot be renamed; create a new one instead.", code="preset_rename", details={"fields": {"name": "Cannot change"}})
        return self._write(data, new=False)

    def delete(self, preset_id: str) -> None:
        preset = self.get(preset_id)
        require_custom(preset.extension, f"{self.kind.capitalize()} presets")
        (self.root / preset.extension / f"{preset.name}.json").unlink()
