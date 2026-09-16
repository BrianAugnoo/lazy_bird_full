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


def auto_embedding() -> list[int]:
    if not auto_embedding_enabled():
        return []

    from lazy_bird.crud.file import enqueue_files_requiring_embedding

    return enqueue_files_requiring_embedding()


def apply_preferences() -> list[int]:
    if auto_embedding_enabled():
        return auto_embedding()
    return []

