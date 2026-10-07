from pathlib import Path
from typing import Any

import yaml


PREFERENCE_FILE = Path(__file__).with_name("preference.yaml")


def _read_preferences() -> dict[str, Any]:
    if not PREFERENCE_FILE.exists():
        return {}
    with PREFERENCE_FILE.open(encoding="utf-8") as preference_file:
        values = yaml.safe_load(preference_file) or {}
    if not isinstance(values, dict):
        raise ValueError("preference.yaml must contain a mapping")
    return values


def get_preferences() -> dict[str, Any]:
    return _read_preferences()


def update_preferences(values: dict[str, Any]) -> bool:
    current = _read_preferences()
    if current == values:
        return False
    PREFERENCE_FILE.write_text(
        yaml.safe_dump(values, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )
    return True


def auto_embedding_enabled() -> bool:
    auto_embedding = _read_preferences().get("auto-embedding", {})
    if not isinstance(auto_embedding, dict):
        raise ValueError("preference.yaml: auto-embedding must contain a mapping")
    enabled = auto_embedding.get("enable", auto_embedding.get("enabled", True))
    if not isinstance(enabled, bool):
        raise ValueError("preference.yaml: auto-embedding.enable must be a boolean")
    return enabled


DEFAULT_CHUNK_MAX_TOKENS = 512


def chunking_max_tokens() -> int:
    """Token budget of one chunk (``chunking.max_tokens``), independent of embedding models."""
    chunking = _read_preferences().get("chunking", {})
    if not isinstance(chunking, dict):
        raise ValueError("preference.yaml: chunking must contain a mapping")
    value = chunking.get("max_tokens", DEFAULT_CHUNK_MAX_TOKENS)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 1:
        raise ValueError("preference.yaml: chunking.max_tokens must be an integer greater than 1")
    return value


DEFAULT_TASK_WORKERS = 4


def task_preferences() -> dict[str, Any]:
    """``tasks.workers`` (parallel runs) and ``tasks.resources`` (capacity overrides)."""
    tasks = _read_preferences().get("tasks", {}) or {}
    if not isinstance(tasks, dict):
        raise ValueError("preference.yaml: tasks must contain a mapping")
    workers = tasks.get("workers", DEFAULT_TASK_WORKERS)
    if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
        raise ValueError("preference.yaml: tasks.workers must be a positive integer")
    resources = tasks.get("resources", {}) or {}
    if not isinstance(resources, dict) or not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in resources.values()):
        raise ValueError("preference.yaml: tasks.resources must map resource names to numbers")
    return {"workers": workers, "resources": {name: float(value) for name, value in resources.items()}}


DEFAULT_SCAN_MINUTES = 10


def scan_every_minutes() -> int:
    """``files.scan_every_minutes``: how often files are checked for changes on disk (0 = never)."""
    files = _read_preferences().get("files", {}) or {}
    if not isinstance(files, dict):
        raise ValueError("preference.yaml: files must contain a mapping")
    value = files.get("scan_every_minutes", DEFAULT_SCAN_MINUTES)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("preference.yaml: files.scan_every_minutes must be a non-negative integer")
    return value


def apply_preferences() -> int:
    """Queue what the preferences ask for; return how many processing tasks were queued.

    - auto-embedding: every file gets its chunks and the vectors of the default
      embedding preset;
    - files.scan_every_minutes: a periodic scan detects files changed on disk.
    """
    from lazy_bird.crud import file_processing
    from lazy_bird.tasks.default.files import schedule_scan

    queued = file_processing.ensure_all() if auto_embedding_enabled() else 0
    minutes = scan_every_minutes()
    schedule_scan(minutes)
    return queued
