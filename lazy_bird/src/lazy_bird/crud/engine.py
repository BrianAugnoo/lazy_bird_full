"""Engines and their presets, shared by every engine family (embedding, inference...).

An engine family is a flat package of engine modules (``embedding/engines/``,
``inference/engines/``) plus two tables: one row per discovered engine and any
number of presets (named kwargs) per engine. Each module must define:

- ``name``: unique engine name;
- ``EngineSettings``: pydantic model of its configuration (see ``extension.settings``);
- ``fields`` (optional): widget overrides for some ``EngineSettings`` attributes;
- ``formats`` (required when ``EngineSettings`` has ``model_id``): model formats the
  engine can load, compared case-insensitively with ``LLMModel.selected_format``;
- the family-specific functions listed in ``EngineFamily.required``.

When ``EngineSettings`` declares ``model_id``, the attribute references an
``LLMModel``: the family checks it exists and that the engine supports its format,
then hands the resolved model to the engine.

Preset invariant: whenever presets exist, exactly one of them is the default.
The database forbids two defaults; this module makes sure one always exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel, select

from lazy_bird.crud import llm_model as llm_model_crud
from lazy_bird.database import db
from lazy_bird.errors import ConflictError, InvalidSettingsError, NotFoundError, UnavailableError
from lazy_bird.extension import ExtensionContractError
from lazy_bird.extension.discovery import (
    LoadFailure,
    import_module,
    iter_package_modules,
    record_failures,
    require_attributes,
)
from lazy_bird.extension.settings import ROOT_ERROR_KEY, SettingsContract, settings_contract
from lazy_bird.schemas.engine import EngineOut
from lazy_bird.schemas.llm_model import LLMModelOut

MODEL_ATTRIBUTE = "model_id"


@dataclass(frozen=True)
class LoadedEngine:
    module: ModuleType
    contract: SettingsContract

    @property
    def formats(self) -> list[str]:
        return list(getattr(self.module, "formats", []) or [])


@dataclass(frozen=True)
class ResolvedEngine:
    """Everything needed to call an engine: its module, parsed settings and model."""

    engine: EngineOut
    module: ModuleType
    settings: BaseModel
    model: LLMModelOut | None
    preset_id: int | None = None


class EngineFamily:
    def __init__(
        self,
        *,
        kind: str,
        package: str,
        required: tuple[str, ...],
        engine_table: type[SQLModel],
        preset_table: type[SQLModel],
        engine_fk: str,
        preset_out: type[BaseModel],
        on_default_change: Callable[[], None] | None = None,
    ) -> None:
        self.kind = kind
        self.package = package
        self.required = required
        self.engine_table = engine_table
        self.preset_table = preset_table
        self.engine_fk = engine_fk
        self.preset_out = preset_out
        self.on_default_change = on_default_change
        self._loaded: dict[str, LoadedEngine] = {}

    # ----------------------------------------------------------------- discovery
    def load_module(self, import_path: str) -> LoadedEngine:
        """Import one engine module and check its contract."""
        return self.check_module(import_module(import_path))

    def check_module(self, module: ModuleType) -> LoadedEngine:
        """Check that a module respects the engine contract of this family."""
        require_attributes(module, ("name", "EngineSettings", *self.required))
        contract = settings_contract(module, "EngineSettings", required=True)
        loaded = LoadedEngine(module, contract)
        if contract.has(MODEL_ATTRIBUTE) and not loaded.formats:
            raise ExtensionContractError(f"EngineSettings declares '{MODEL_ATTRIBUTE}' but 'formats' is empty")
        return loaded

    def discover(self) -> list[EngineOut]:
        """Load every engine module of the package and upsert its row."""
        self._loaded.clear()
        failures = []
        for import_path in iter_package_modules(self.package):
            try:
                loaded = self.load_module(import_path)
            except Exception as error:
                failures.append(LoadFailure(f"{self.kind}_engine", import_path, str(error)))
                continue
            self._register(loaded)
        record_failures(f"{self.kind}_engine", failures)
        return self.engines()

    def register(self, module: ModuleType) -> EngineOut:
        """Register an engine module that does not live in the engines package."""
        loaded = self.check_module(module)
        self._register(loaded)
        return next(engine for engine in self.engines() if engine.name == module.name)

    def _register(self, loaded: LoadedEngine) -> None:
        self._loaded[loaded.module.name] = loaded
        source = getattr(loaded.module, "__file__", None)
        self._upsert(loaded, Path(source).name if source else loaded.module.__name__)

    def _upsert(self, loaded: LoadedEngine, file_path: str) -> None:
        with db() as session:
            row = session.exec(select(self.engine_table).where(self.engine_table.name == loaded.module.name)).first()
            if row is None:
                row = self.engine_table(name=loaded.module.name)
            row.file_path = file_path
            row.formats = loaded.formats
            row.kwargs_key = loaded.contract.kwargs_key()
            session.add(row)
            session.commit()

    # ------------------------------------------------------------------- engines
    def _engine_out(self, row: SQLModel) -> EngineOut:
        engine = EngineOut.model_validate(row)
        return engine.model_copy(update={"available": row.name in self._loaded})

    def engines(self) -> list[EngineOut]:
        with db() as session:
            rows = session.exec(select(self.engine_table).order_by(self.engine_table.name)).all()
            return [self._engine_out(row) for row in rows]

    def engine(self, engine_id: int) -> EngineOut:
        with db() as session:
            row = session.get(self.engine_table, engine_id)
            if row is None:
                raise NotFoundError(f"{self.kind.capitalize()} engine", engine_id, code="engine_not_found")
            return self._engine_out(row)

    def loaded(self, engine: EngineOut) -> LoadedEngine:
        """Return the module of an engine, or raise when it is not importable anymore."""
        loaded = self._loaded.get(engine.name)
        if loaded is None:
            raise UnavailableError(
                f"{self.kind.capitalize()} engine '{engine.name}' is not available (its module failed to load or was removed).",
                code="engine_unavailable",
                details={"engine_id": engine.id, "engine": engine.name},
            )
        return loaded

    # ----------------------------------------------------------------- settings
    def _model(self, loaded: LoadedEngine, settings: BaseModel) -> LLMModelOut | None:
        """Resolve ``settings.model_id`` into an LLM model the engine can load."""
        if not loaded.contract.has(MODEL_ATTRIBUTE):
            return None
        model_id = getattr(settings, MODEL_ATTRIBUTE)
        if model_id is None:
            return None
        model = llm_model_crud.find(model_id)
        if model is None:
            raise InvalidSettingsError({MODEL_ATTRIBUTE: f"Model {model_id} does not exist"})
        supported = {value.lower() for value in loaded.formats}
        if (model.selected_format or "").lower() not in supported:
            raise InvalidSettingsError(
                {MODEL_ATTRIBUTE: f"Format '{model.selected_format}' of model {model_id} is not supported (supported: {', '.join(loaded.formats)})"}
            )
        return model

    def check_kwargs(self, engine: EngineOut, kwargs: dict[str, Any] | None) -> dict[str, Any]:
        """Validate kwargs for an engine and return their normalized storable form."""
        loaded = self.loaded(engine)
        settings = loaded.contract.validate(kwargs)
        self._model(loaded, settings)
        return loaded.contract.dump(settings)

    def resolve_settings(self, engine_id: int, kwargs: dict[str, Any] | None, preset_id: int | None = None) -> ResolvedEngine:
        """Build a callable engine from an engine id and raw kwargs."""
        engine = self.engine(engine_id)
        loaded = self.loaded(engine)
        settings = loaded.contract.validate(kwargs)
        return ResolvedEngine(engine, loaded.module, settings, self._model(loaded, settings), preset_id)

    # ------------------------------------------------------------------- presets
    def _preset_errors(self, row: SQLModel) -> dict[str, str]:
        try:
            self.check_kwargs(self.engine(getattr(row, self.engine_fk)), row.kwargs)
        except InvalidSettingsError as error:
            return error.fields
        except (UnavailableError, NotFoundError) as error:
            return {ROOT_ERROR_KEY: error.message}
        return {}

    def _preset_out(self, row: SQLModel) -> BaseModel:
        errors = self._preset_errors(row)
        return self.preset_out.model_validate(
            {**row.model_dump(), "valid": not errors, "errors": errors}
        )

    def _preset_row(self, session, preset_id: int) -> SQLModel:
        row = session.get(self.preset_table, preset_id)
        if row is None:
            raise NotFoundError(f"{self.kind.capitalize()} preset", preset_id, code="preset_not_found")
        return row

    def presets(self) -> list[BaseModel]:
        with db() as session:
            rows = session.exec(select(self.preset_table).order_by(self.preset_table.id)).all()
        return [self._preset_out(row) for row in rows]

    def preset(self, preset_id: int) -> BaseModel:
        with db() as session:
            row = self._preset_row(session, preset_id)
        return self._preset_out(row)

    def default_preset(self) -> BaseModel | None:
        with db() as session:
            row = session.exec(select(self.preset_table).where(self.preset_table.default == True)).first()  # noqa: E712
        return self._preset_out(row) if row else None

    def _clear_default(self, session) -> None:
        for row in session.exec(select(self.preset_table).where(self.preset_table.default == True)).all():  # noqa: E712
            row.default = False
            session.add(row)
        session.flush()

    def _commit(self, session, name: str) -> None:
        try:
            session.commit()
        except IntegrityError as error:
            session.rollback()
            raise ConflictError(
                f"The {self.kind} preset name '{name}' is already taken.",
                code="preset_name_taken",
                details={"name": name},
            ) from error

    def create_preset(self, name: str, engine_id: int, kwargs: dict[str, Any], default: bool = False) -> BaseModel:
        normalized = self.check_kwargs(self.engine(engine_id), kwargs)
        with db() as session:
            has_default = session.exec(select(self.preset_table).where(self.preset_table.default == True)).first() is not None  # noqa: E712
            if default:
                self._clear_default(session)
            row = self.preset_table(name=name, kwargs=normalized, default=default or not has_default)
            setattr(row, self.engine_fk, engine_id)
            session.add(row)
            self._commit(session, name)
            session.refresh(row)
        if row.default:
            self._default_changed()
        return self._preset_out(row)

    def _default_changed(self) -> None:
        if self.on_default_change is not None:
            self.on_default_change()

    def update_preset(self, preset_id: int, changes: dict[str, Any]) -> BaseModel:
        with db() as session:
            row = self._preset_row(session, preset_id)
            engine_id = changes.get(self.engine_fk) or getattr(row, self.engine_fk)
            if self.engine_fk in changes or changes.get("kwargs") is not None:
                kwargs = changes["kwargs"] if changes.get("kwargs") is not None else row.kwargs
                row.kwargs = self.check_kwargs(self.engine(engine_id), kwargs)
                setattr(row, self.engine_fk, engine_id)
            if changes.get("name") is not None:
                row.name = changes["name"]
            if changes.get("default") is True and not row.default:
                self._clear_default(session)
                row.default = True
            elif changes.get("default") is False and row.default:
                raise ConflictError(
                    f"A default {self.kind} preset is required; mark another preset as default instead.",
                    code="default_preset_required",
                )
            session.add(row)
            self._commit(session, row.name)
            session.refresh(row)
        if row.default and (changes.get("default") is True or "kwargs" in changes or self.engine_fk in changes):
            self._default_changed()
        return self._preset_out(row)

    def delete_preset(self, preset_id: int) -> None:
        """Delete a preset; when it was the default, the oldest remaining preset becomes default."""
        with db() as session:
            row = self._preset_row(session, preset_id)
            was_default = row.default
            session.delete(row)
            session.flush()
            if was_default:
                successor = session.exec(select(self.preset_table).order_by(self.preset_table.id)).first()
                if successor is not None:
                    successor.default = True
                    session.add(successor)
            session.commit()
        if was_default:
            self._default_changed()

    def resolve(self, preset_id: int | None = None) -> ResolvedEngine:
        """Return the callable engine of a preset (the default preset when ``preset_id`` is None)."""
        if preset_id is None:
            preset = self.default_preset()
            if preset is None:
                raise UnavailableError(
                    f"No {self.kind} preset exists yet. Create one to use {self.kind}.",
                    code=f"no_default_{self.kind}_preset",
                )
        else:
            preset = self.preset(preset_id)
        if not preset.valid:
            raise InvalidSettingsError(preset.errors, message=f"{self.kind.capitalize()} preset '{preset.name}' is invalid.")
        return self.resolve_settings(getattr(preset, self.engine_fk), preset.kwargs, preset.id)
