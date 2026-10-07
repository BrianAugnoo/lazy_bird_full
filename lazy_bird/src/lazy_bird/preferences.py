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


def auto_embedding() -> list[int]:
    if not auto_embedding_enabled():
        return []

    from lazy_bird.crud.file import enqueue_files_requiring_embedding

    return enqueue_files_requiring_embedding()


def apply_preferences() -> list[int]:
    if auto_embedding_enabled():
        return auto_embedding()
    return []

