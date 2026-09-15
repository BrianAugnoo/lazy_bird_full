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


def auto_embedding_enabled() -> bool:
    auto_embedding = _read_preferences().get("auto-embedding", {})
    if not isinstance(auto_embedding, dict):
        raise ValueError("preference.yaml: auto-embedding must contain a mapping")
    enabled = auto_embedding.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ValueError("preference.yaml: auto-embedding.enabled must be a boolean")
    return enabled