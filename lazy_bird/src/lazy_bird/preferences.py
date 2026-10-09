"""Runtime preferences stored in ``preference.yaml``.

The file has one mapping per section; ``SECTIONS`` declares them with a pydantic
model each, so values are validated and missing ones take their default. The
frontend edits them with the generic settings form (``kwargs_key`` per section).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from lazy_bird.errors import AppError, InvalidInputError, InvalidSettingsError
from lazy_bird.extension.settings import SettingsContract

PREFERENCE_FILE = Path(__file__).with_name("preference.yaml")


class InvalidPreferencesError(AppError):
    """``preference.yaml`` was edited by hand into an invalid state."""

    status_code = 500
    code = "invalid_preferences"


class AutoEmbedding(BaseModel):
    enable: bool = Field(default=True, description="Chunk and embed every new or changed file automatically.")
    model_config = ConfigDict(extra="forbid")


class Chunking(BaseModel):
    max_tokens: int = Field(default=512, ge=2, description="Token budget of one chunk.")
    model_config = ConfigDict(extra="forbid")


class Files(BaseModel):
    scan_every_minutes: int = Field(default=10, ge=0, description="How often stored files are checked for changes on disk (0 = only at startup).")
    model_config = ConfigDict(extra="forbid")


class Tasks(BaseModel):
    workers: int = Field(default=4, ge=1, description="Background tasks running at the same time (applied at restart).")
    resources: dict[str, float] = Field(default_factory=dict, description='Capacity overrides, e.g. {"vram_mb": 12000}.')
    model_config = ConfigDict(extra="forbid")


class SmartMemory(BaseModel):
    enable: bool = Field(
        default=True,
        title="Supervise memory",
        description="Watch the memory of this computer (RAM and GPU memory): models and tasks wait, make room or move to the CPU instead of overloading it. Off, everything runs unsupervised, at the risk of a crash.",
    )
    fallback: Literal["cpu", "wait"] = Field(
        default="wait",
        title="Fallback policy",
        description="When a model does not fit in GPU memory right now: 'cpu' loads it in RAM instead, 'wait' waits until GPU memory is free. Only applies to engines whose device is left empty.",
    )
    interrupt_timeout_seconds: int = Field(
        default=60,
        ge=1,
        title="Time to make room (seconds)",
        description="How long a task asked to make room for a more urgent one may take to reach its next stopping point before it is reported as not responding.",
    )
    model_config = ConfigDict(extra="forbid")


SECTIONS: dict[str, tuple[type[BaseModel], str]] = {
    "auto-embedding": (AutoEmbedding, "Automatic processing"),
    "chunking": (Chunking, "Chunking"),
    "files": (Files, "Files"),
    "tasks": (Tasks, "Background tasks"),
    "smart-memory": (SmartMemory, "Smart memory management"),
}
RESTART_REQUIRED = {("tasks", "workers")}


def _read_preferences() -> dict[str, Any]:
    if not PREFERENCE_FILE.exists():
        return {}
    try:
        values = yaml.safe_load(PREFERENCE_FILE.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as error:
        raise InvalidPreferencesError(f"preference.yaml is not valid YAML: {error}") from error
    if not isinstance(values, dict):
        raise InvalidPreferencesError("preference.yaml must contain a mapping.")
    return values


def _section(values: dict[str, Any], name: str) -> BaseModel:
    model = SECTIONS[name][0]
    try:
        return SettingsContract(model).validate(values.get(name) or {})
    except InvalidSettingsError as error:
        raise InvalidPreferencesError(f"preference.yaml, section '{name}': {error.message}", details={"fields": error.fields}) from error


def get_preferences() -> dict[str, dict[str, Any]]:
    """Every section with its values (defaults filled in)."""
    values = _read_preferences()
    return {name: _section(values, name).model_dump() for name in SECTIONS}


def form() -> dict[str, dict[str, Any]]:
    """The settings form of every section: ``{section: {"title", "kwargs_key"}}``."""
    return {name: {"title": title, "kwargs_key": SettingsContract(model).kwargs_key()} for name, (model, title) in SECTIONS.items()}


def update_preferences(changes: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Merge changes (``{section: {key: value}}``) into the file.

    Returns the new preferences and the keys that only apply after a restart.
    Raises ``InvalidInputError`` with one message per invalid key.
    """
    unknown = [name for name in changes if name not in SECTIONS]
    if unknown:
        raise InvalidInputError(f"Unknown preference section(s): {', '.join(unknown)}.", code="unknown_preference", details={"fields": {name: "Unknown section" for name in unknown}})
    current = get_preferences()
    merged, errors = {}, {}
    for name, (model, _) in SECTIONS.items():
        candidate = {**current[name], **(changes.get(name) or {})}
        try:
            merged[name] = SettingsContract(model).validate(candidate).model_dump()
        except InvalidSettingsError as error:
            errors.update({f"{name}.{key}": message for key, message in error.fields.items()})
    if errors:
        raise InvalidInputError("Some preferences are invalid.", code="invalid_preferences", details={"fields": errors})
    PREFERENCE_FILE.write_text(yaml.safe_dump(merged, sort_keys=False, allow_unicode=True), encoding="utf-8")
    restart = [f"{section}.{key}" for section, key in RESTART_REQUIRED if merged[section][key] != current[section][key]]
    return merged, restart


def auto_embedding_enabled() -> bool:
    return _section(_read_preferences(), "auto-embedding").enable


def chunking_max_tokens() -> int:
    """Token budget of one chunk (``chunking.max_tokens``), independent of embedding models."""
    return _section(_read_preferences(), "chunking").max_tokens


def scan_every_minutes() -> int:
    """``files.scan_every_minutes``: how often files are checked for changes on disk (0 = never)."""
    return _section(_read_preferences(), "files").scan_every_minutes


def task_preferences() -> dict[str, Any]:
    """``tasks.workers`` (parallel runs) and ``tasks.resources`` (capacity overrides)."""
    return _section(_read_preferences(), "tasks").model_dump()


def smart_memory() -> SmartMemory:
    """The ``smart-memory`` section: whether memory is supervised, and how."""
    return _section(_read_preferences(), "smart-memory")


def apply_preferences() -> int:
    """Queue what the preferences ask for; return how many processing tasks were queued.

    - auto-embedding: every file gets its chunks and the vectors of the default
      embedding preset;
    - files.scan_every_minutes: a periodic scan detects files changed on disk;
    - tasks.resources: capacity overrides of the running scheduler;
    - smart-memory: models kept loaded while idle are released when it is turned off.
    """
    from lazy_bird import tasks
    from lazy_bird.crud import file_processing
    from lazy_bird.tasks.default.files import schedule_scan
    from lazy_bird.residency import residency
    from lazy_bird.tasks.resources import detect_capacity

    queued = file_processing.ensure_all() if auto_embedding_enabled() else 0
    schedule_scan(scan_every_minutes())
    if tasks._scheduler is not None:
        tasks._scheduler.pool.capacity.update({**detect_capacity(), **task_preferences()["resources"]})
    if not smart_memory().enable:
        residency().release_idle()
    return queued
